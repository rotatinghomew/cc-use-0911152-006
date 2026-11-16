from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from basin_warning.command_center import Application
from basin_warning.observations.hydro_event import ContractError, DomainRecord
from basin_warning.replay.replay_engine import replay_candidate
from basin_warning.replay.rule_package import RulePackage, baseline_package
from basin_warning.replay.timeline_store import Repository

from tests.replay._helpers import (
    approve_set,
    build_eligible_candidate,
    labels_for_approve_set,
    numeric_records,
)


class ShadowIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "live.sqlite3"
        self.application = Application(self.database)
        self.records = numeric_records()
        good = build_eligible_candidate(self.records, None)
        event_ids = approve_set(self.records, dict(good.context_overrides), 0.78)
        self.labels = labels_for_approve_set(self.records, event_ids)

    def test_trial_database_is_separate_from_live(self):
        self.application.run_replay(
            self.records, self.labels,
            RulePackage("cand-unsaved", 1, {"approve_threshold": 0.5}), save=False,
        )
        self.assertIsNone(self.application.trial_store.active_basis())
        candidate = RulePackage("cand-saved", 1, {"approve_threshold": 0.5})
        self.application.run_replay(self.records, self.labels, candidate)
        trial_path = Path(str(self.database).replace(".sqlite3", ".trial.sqlite3"))
        self.assertTrue(trial_path.is_file())
        self.assertNotEqual(trial_path, self.database)
        # Live tables remain untouched by trial activity.
        self.assertEqual(self.application.repository.snapshot()["counts"]["records"], 0)

    def test_replay_never_writes_live_decisions(self):
        candidate = RulePackage("cand", 1, {"approve_threshold": 0.4})
        self.application.run_replay(self.records, self.labels, candidate)
        self.assertEqual(self.application.repository.snapshot()["counts"]["decisions"], 0)
        self.assertEqual(self.application.repository.verify_chain(), [])


class RuleBasisTraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.application = Application(self.root / "live.sqlite3")
        self.records = numeric_records()
        good = build_eligible_candidate(self.records, None)
        self.overrides = dict(good.context_overrides)
        event_ids = approve_set(self.records, self.overrides, 0.78)
        self.labels = labels_for_approve_set(self.records, event_ids)

    def test_decision_without_enabled_package_uses_baseline_basis(self):
        _, decision = self.application.process(self.records[0])
        self.assertEqual(decision.rule_basis["package_id"], baseline_package().package_id)

    def test_old_notice_traces_to_original_basis_after_switch(self):
        for record in self.records:
            self.application.ingest(record)
        record = self.records[0]
        repo = self.application.repository
        repo.register_reach("reach-a", None, 2.0)
        repo.assign_station(str(record.payload["station_id"]), "reach-a")
        repo.issue_notice("notice-old", "reach-a", record.record_id, record.version)
        old_notice = repo.reach_notices("reach-a")[0]
        self.assertEqual(
            json.loads(old_notice["rule_basis_json"])["package_id"],
            baseline_package().package_id,
        )

        candidate = RulePackage("candidate-switch", 1, self.overrides,
                                alert_outcomes=("approve",))
        report = self.application.run_replay(self.records, self.labels, candidate)
        self.assertTrue(report.eligibility.eligible, report.eligibility.blocking_reasons)
        review_id = self.application.submit_candidate(
            candidate, report.replay_id, "li", "evidence backed"
        )
        self.application.decide_candidate_review(review_id, True, "wang", "approved")
        self.application.enable_candidate(candidate, "zhao")

        fresh = DomainRecord(
            "hazard-window-fresh", dict(record.payload) | {"station_id": "station-fresh"},
            "observing", occurred_at="2026-11-16T08:00:00+00:00",
        )
        _, new_decision = self.application.process(fresh)
        self.assertEqual(new_decision.rule_basis["package_id"], "candidate-switch")

        repo.update_notice("notice-old", "delivered")
        traceable = repo.reach_notices("reach-a")[0]
        self.assertEqual(traceable["status"], "delivered")
        self.assertEqual(
            json.loads(traceable["rule_basis_json"])["package_id"],
            baseline_package().package_id,
        )

    def test_legacy_database_migrates_and_keeps_old_rows_null(self):
        legacy_path = self.root / "legacy.sqlite3"
        repository = Repository(legacy_path)
        record = self.records[0]
        repository.save_record(record)
        repository.register_reach("reach-legacy", None, 1.0)
        repository.assign_station(str(record.payload["station_id"]), "reach-legacy")
        with sqlite3.connect(legacy_path) as connection:
            connection.execute("ALTER TABLE alert_notices RENAME TO alert_notices_old")
            connection.execute(
                "CREATE TABLE alert_notices AS SELECT notice_id,reach_id,observation_id,"
                "observation_version,status,issued_at,delivered_at,acknowledged_at "
                "FROM alert_notices_old"
            )
            connection.execute("DROP TABLE alert_notices_old")
        reopened = Repository(legacy_path)
        notice = reopened.issue_notice(
            "legacy-notice", "reach-legacy", record.record_id, record.version
        )
        self.assertEqual(
            json.loads(notice["rule_basis_json"])["package_id"],
            baseline_package().package_id,
        )


class CorrectionRevocationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.application = Application(Path(self.temp.name) / "live.sqlite3")
        self.records = numeric_records()
        good = build_eligible_candidate(self.records, None)
        self.overrides = dict(good.context_overrides)
        event_ids = approve_set(self.records, self.overrides, 0.78)
        self.labels = labels_for_approve_set(self.records, event_ids)
        for record in self.records:
            self.application.ingest(record)

    def _enable(self, package_id):
        candidate = RulePackage(package_id, 1, self.overrides, alert_outcomes=("approve",))
        report = self.application.run_replay(self.records, self.labels, candidate)
        self.assertTrue(report.eligibility.eligible, report.eligibility.blocking_reasons)
        review_id = self.application.submit_candidate(
            candidate, report.replay_id, "li", "evidence backed"
        )
        self.application.decide_candidate_review(review_id, True, "wang", "approved")
        self.application.enable_candidate(candidate, "zhao")
        return candidate, report

    def test_correction_revokes_enabled_candidate_and_keeps_live_chain_intact(self):
        candidate, report = self._enable("candidate-correct")
        self.assertIsNotNone(self.application.trial_store.active_basis())
        corrected = self.records[0].with_payload({"rainfall_mm": 999.0})
        result = self.application.record_observation_correction(corrected, "gauge corrected")
        self.assertIn(report.replay_id, result["invalidated_replays"])
        self.assertIsNotNone(result["revocation"])
        self.assertIsNone(self.application.trial_store.active_basis())
        self.assertEqual(
            self.application.trial_store.package_status("candidate-correct", 1), "revoked"
        )
        self.assertEqual(self.application.repository.verify_chain(), [])
        self.assertEqual(self.application.trial_store.verify_trial_chain(), [])
        history = self.application.trial_store.review_history("candidate-correct", 1)
        revoked = next(row for row in history if row["action"] == "revoked")
        self.assertIn("gauge corrected", revoked["detail"]["reason"])

    def test_enable_blocked_when_evidence_version_drifts(self):
        # Advance a live record after the first enablement, then build a second
        # candidate whose replay pins the OLD versions so enablement must fail.
        self._enable("candidate-drift-base")
        advanced = self.records[0].with_state("watch")
        self.application.repository.save_record(
            advanced, expected_version=self.records[0].version
        )
        stale_records = self.records  # pre-advance fingerprints captured here
        second = RulePackage("candidate-drift", 2,
                             dict(self.overrides) | {"review_threshold": 0.05},
                             alert_outcomes=("approve",))
        report = replay_candidate(stale_records, self.labels, second)
        if report.eligibility.eligible:
            self.application.trial_store.register_package(second)
            self.application.trial_store.save_replay(
                report,
                observed_versions={record.record_id: record.version for record in stale_records},
            )
            review_id = self.application.submit_candidate(
                second, report.replay_id, "li", "evidence backed"
            )
            self.application.decide_candidate_review(review_id, True, "wang", "approved")
            with self.assertRaisesRegex(ContractError, "enable blocked"):
                self.application.enable_candidate(second, "zhao")

    def test_superseded_package_is_replaced_not_duplicated(self):
        first, _ = self._enable("candidate-one")
        second = RulePackage("candidate-two", 1,
                             dict(self.overrides) | {"review_threshold": 0.02},
                             alert_outcomes=("approve",))
        report = self.application.run_replay(self.records, self.labels, second)
        self.assertTrue(report.eligibility.eligible, report.eligibility.blocking_reasons)
        review_id = self.application.submit_candidate(
            second, report.replay_id, "li", "better evidence"
        )
        self.application.decide_candidate_review(review_id, True, "wang", "approved")
        self.application.enable_candidate(second, "zhao")
        self.assertEqual(self.application.trial_store.active_basis()["package_id"],
                         "candidate-two")
        self.assertEqual(
            self.application.trial_store.package_status("candidate-one", 1), "superseded"
        )


if __name__ == "__main__":
    unittest.main()
