from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from basin_warning.observations.hydro_event import ContractError, Decision, DomainRecord, records_from_fixture, stable_hash
from basin_warning.replay.timeline_store import Repository
from basin_warning.alerts.escalation import advance_for_outcome, decide
from basin_warning.review.incident_report import export_bundle, verify_bundle
from basin_warning.fusion.watermark import derive_context
from basin_warning.replay.rule_package import RulePackage, baseline_package
from basin_warning.replay.trial_store import TrialStore
from basin_warning.replay.replay_engine import (
    ReplayReport,
    TrialPolicy,
    replay_candidate,
)


class Application:
    def __init__(self, database: str | Path, context: Mapping[str, Any] | None = None,
                 trial_database: str | Path | None = None):
        self.repository = Repository(database)
        self.context = dict(context or {})
        # The trial store defaults to a sibling database so shadow work never
        # shares tables (or the audit chain) with the live repository.
        self.trial_store = TrialStore(trial_database or str(Path(database).with_suffix(".trial.sqlite3")))

    # ------------------------------------------------------------- live pipeline
    def active_package(self) -> RulePackage:
        package = self.trial_store.active_package()
        return package or baseline_package()

    def _live_context(self, stored: DomainRecord) -> dict[str, Any]:
        context = dict(self.context)
        context.update(derive_context(stored, self.repository))
        package = self.active_package()
        # Enabled-package tuning applies only to fresh decisions; stored
        # decisions and already issued notices keep their original rule basis.
        return context | dict(package.context_overrides)

    def ingest(self, record: DomainRecord) -> DomainRecord:
        current = self.repository.get_record(record.record_id)
        if current is None:
            self.repository.save_record(record)
            return record
        if current.fingerprint == record.fingerprint:
            return current
        replacement = DomainRecord(record.record_id, record.payload, current.state,
                                   current.version + 1, record.occurred_at, record.source)
        self.repository.save_record(replacement, expected_version=current.version)
        return replacement

    def process(self, record: DomainRecord) -> tuple[DomainRecord, Decision]:
        stored = self.ingest(record)
        context = self._live_context(stored)
        decision = decide(stored, context, rule_basis=self.active_package().basis())
        self.repository.save_decision(decision)
        advanced = advance_for_outcome(stored, decision)
        if advanced.fingerprint != stored.fingerprint:
            self.repository.save_record(advanced, expected_version=stored.version)
        return advanced, decision

    def run_fixture(self, fixture: Mapping[str, Any], output: str | Path) -> dict[str, Any]:
        records = records_from_fixture(fixture)
        fixture_hash = stable_hash(fixture)
        run_id = self.repository.begin_run(fixture_hash, len(records))
        completed = self.repository.completed_run(run_id)
        if completed is not None:
            return completed
        decisions: dict[str, Decision] = {}
        final_records: list[DomainRecord] = []
        for record in records:
            final_record, decision = self.process(record)
            final_records.append(final_record)
            decisions[record.record_id] = decision
        snapshot = self.repository.snapshot()
        if snapshot["chain_errors"]:
            raise ContractError("audit chain verification failed")
        manifest = export_bundle(output, final_records, decisions, snapshot, self.repository.event_rows())
        result = {"run_id": run_id, "fixture_hash": fixture_hash, "records": len(final_records),
                  "decisions": len(decisions), "manifest": manifest, "snapshot": snapshot}
        self.repository.finish_run(run_id, result)
        return result

    def inspect(self) -> dict[str, Any]:
        return {"snapshot": self.repository.snapshot(), "records": [record.__dict__ for record in self.repository.list_records()],
                "decisions": self.repository.decision_rows()}

    def reach_notices(self, reach_id: str) -> list[dict[str, Any]]:
        return self.repository.reach_notices(reach_id)

    # ------------------------------------------------------------ shadow replay
    def run_replay(
        self,
        records: list[DomainRecord],
        labels: Mapping[str, Any],
        candidate: RulePackage,
        policy: TrialPolicy | None = None,
        save: bool = True,
    ) -> ReplayReport:
        """Replay under baseline vs candidate using the same base engine context."""
        report = replay_candidate(records, labels, candidate, self.context, policy)
        if save:
            self.trial_store.register_package(candidate)
            observed_versions = {
                record.record_id: record.version
                for record in records
                if record.record_id in report.observation_fingerprints
            }
            self.trial_store.save_replay(report, observed_versions=observed_versions)
        return report

    def run_replay_portfolio(
        self,
        records: list[DomainRecord],
        labels: Mapping[str, Any],
        candidates: list[RulePackage],
        policy: TrialPolicy | None = None,
    ) -> list[ReplayReport]:
        return [self.run_replay(records, labels, candidate, policy) for candidate in candidates]

    def submit_candidate(
        self,
        candidate: RulePackage,
        replay_id: str,
        decided_by: str,
        rationale: str,
    ) -> str:
        self.trial_store.register_package(candidate)
        return self.trial_store.submit_for_review(
            candidate.package_id, candidate.version, replay_id, decided_by, rationale
        )

    def decide_candidate_review(
        self, review_id: str, approve: bool, decided_by: str, rationale: str
    ) -> dict[str, Any]:
        return self.trial_store.decide_review(review_id, approve, decided_by, rationale, self.repository)

    def enable_candidate(self, candidate: RulePackage, actor: str) -> dict[str, Any]:
        # Read-only verification against the live repository happens inside the
        # trial store; live rows are never modified by this call.
        return self.trial_store.enable_package(
            candidate.package_id, candidate.version, self.repository, actor
        )

    def withdraw_candidate(self, candidate: RulePackage, actor: str, reason: str) -> None:
        self.trial_store.withdraw_candidate(candidate.package_id, candidate.version, actor, reason)

    def record_observation_correction(
        self,
        corrected: DomainRecord,
        reason: str,
    ) -> dict[str, Any]:
        """Ingest a corrected observation, then invalidate dependent trial evidence.

        Live decisions and notices already issued against the old version are not
        rewritten; the correction only invalidates shadow-trial conclusions and
        revokes an enabled candidate whose evidence was overturned.
        """
        previous = self.repository.get_record(corrected.record_id)
        if previous is None:
            raise ContractError("correction requires an existing observation")
        old_fingerprint = previous.fingerprint
        stored = self.ingest(corrected)
        if stored.fingerprint == old_fingerprint:
            raise ContractError("correction does not change the observation fingerprint")
        invalidated = self.trial_store.record_observation_correction(
            corrected.record_id, old_fingerprint, stored.fingerprint, stored.version, reason
        )
        revocation = self.trial_store.revoke_invalid_enabled(self.repository, "trial-system", reason)
        return {
            "record_id": corrected.record_id,
            "old_fingerprint": old_fingerprint,
            "new_fingerprint": stored.fingerprint,
            "version": stored.version,
            "invalidated_replays": invalidated,
            "revocation": revocation,
        }


def load_fixture(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read fixture: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("fixture root must be an object")
    return value


def run(fixture_path: str | Path, database: str | Path, output: str | Path,
        context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return Application(database, context).run_fixture(load_fixture(fixture_path), output)


def verify(database: str | Path, output: str | Path) -> dict[str, Any]:
    repository = Repository(database)
    chain_errors = repository.verify_chain()
    bundle_errors = verify_bundle(output)
    return {"ok": not chain_errors and not bundle_errors, "chain_errors": chain_errors,
            "bundle_errors": bundle_errors, "snapshot": repository.snapshot()}
