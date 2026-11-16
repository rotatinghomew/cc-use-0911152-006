"""Shadow-trial store: replay evidence, enablement review and withdrawal.

The trial store is intentionally a *separate* database from the live
``Repository``.  Replays, candidate reviews and withdrawals only touch trial
tables and the trial audit chain; live alerts, decisions and notices are never
mutated by trial activity.  At enablement time the store reads the live
repository read-only to verify that the observations and rule versions behind a
candidate are still the ones being served.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from basin_warning.observations.hydro_event import (
    ContractError,
    canonical_json,
    identifier,
    stable_hash,
    utc_now,
)
from basin_warning.replay.replay_engine import ReplayReport
from basin_warning.replay.rule_package import (
    BASELINE_PACKAGE_ID,
    RulePackage,
)

TRIAL_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS rule_packages(
    package_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    content_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('candidate','in_review','approved','rejected','enabled','withdrawn','revoked','superseded')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(package_id, version)
);
CREATE TABLE IF NOT EXISTS replay_runs(
    replay_id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL,
    package_version INTEGER NOT NULL,
    baseline_id TEXT NOT NULL,
    baseline_version INTEGER NOT NULL,
    report_json TEXT NOT NULL,
    report_hash TEXT NOT NULL,
    label_hash TEXT NOT NULL,
    eligible INTEGER NOT NULL,
    evidence_valid INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(package_id, package_version) REFERENCES rule_packages(package_id, version)
);
CREATE TABLE IF NOT EXISTS replay_observations(
    replay_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    observation_fingerprint TEXT NOT NULL,
    observed_version INTEGER,
    invalidated_at TEXT,
    PRIMARY KEY(replay_id, record_id),
    FOREIGN KEY(replay_id) REFERENCES replay_runs(replay_id)
);
CREATE TABLE IF NOT EXISTS candidate_reviews(
    review_id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL,
    package_version INTEGER NOT NULL,
    replay_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','withdrawn','revoked')),
    rationale TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY(replay_id) REFERENCES replay_runs(replay_id)
);
CREATE TABLE IF NOT EXISTS enabled_rules(
    package_id TEXT NOT NULL,
    package_version INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    review_id TEXT NOT NULL,
    replay_id TEXT NOT NULL,
    enabled_at TEXT NOT NULL,
    superseded_at TEXT,
    PRIMARY KEY(package_id, package_version)
);
CREATE TABLE IF NOT EXISTS observation_corrections(
    correction_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    old_fingerprint TEXT NOT NULL,
    new_fingerprint TEXT NOT NULL,
    observed_version INTEGER NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_history(
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    package_version INTEGER NOT NULL,
    action TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_events(
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_replay_obs ON replay_observations(record_id, invalidated_at);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON candidate_reviews(status, created_at);
"""

REVIEWABLE_STATUSES = ("candidate",)
ACTIVE_REVIEW_STATUSES = ("submitted",)


class TrialStore:
    def __init__(self, database: str | Path):
        self.database = str(database)
        self._lock = threading.RLock()
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(TRIAL_SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self.connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _last_hash(self, connection: sqlite3.Connection) -> str:
        row = connection.execute(
            "SELECT event_hash FROM trial_events ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else "0" * 64

    def append_event(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        aggregate_id: str,
        aggregate_version: int,
        payload: Mapping[str, Any],
    ) -> str:
        previous = self._last_hash(connection)
        created_at = utc_now()
        event_hash = stable_hash(
            {
                "event_type": event_type,
                "aggregate_id": aggregate_id,
                "aggregate_version": aggregate_version,
                "payload": payload,
                "previous_hash": previous,
                "created_at": created_at,
            }
        )
        connection.execute(
            "INSERT INTO trial_events(event_type,aggregate_id,aggregate_version,payload_json,previous_hash,event_hash,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (
                event_type,
                aggregate_id,
                aggregate_version,
                canonical_json(payload),
                previous,
                event_hash,
                created_at,
            ),
        )
        return event_hash

    def _history(
        self,
        connection: sqlite3.Connection,
        package_id: str,
        package_version: int,
        action: str,
        detail: Mapping[str, Any],
        actor: str,
    ) -> None:
        connection.execute(
            "INSERT INTO review_history(package_id,package_version,action,detail_json,actor,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (
                package_id,
                package_version,
                action,
                canonical_json(detail),
                identifier(actor),
                utc_now(),
            ),
        )

    # ------------------------------------------------------------------ packages
    def register_package(self, package: RulePackage) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT fingerprint,status FROM rule_packages WHERE package_id=? AND version=?",
                (package.package_id, package.version),
            ).fetchone()
            if row:
                if row["fingerprint"] != package.fingerprint:
                    raise ContractError("package version content cannot change")
                return {"package_id": package.package_id, "version": package.version,
                        "status": row["status"], "fingerprint": package.fingerprint}
            connection.execute(
                "INSERT INTO rule_packages(package_id,version,fingerprint,content_json,status,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (
                    package.package_id,
                    package.version,
                    package.fingerprint,
                    canonical_json(package.content),
                    "candidate",
                    utc_now(),
                    utc_now(),
                ),
            )
            self.append_event(
                connection,
                "package.registered",
                package.package_id,
                package.version,
                package.basis(),
            )
            self._history(connection, package.package_id, package.version,
                          "registered", package.basis(), "trial-system")
        return {"package_id": package.package_id, "version": package.version,
                "status": "candidate", "fingerprint": package.fingerprint}

    def get_package(self, package_id: str, version: int) -> RulePackage | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT content_json FROM rule_packages WHERE package_id=? AND version=?",
                (package_id, version),
            ).fetchone()
        if not row:
            return None
        return RulePackage.from_dict(json.loads(row["content_json"]))

    def package_status(self, package_id: str, version: int) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT status FROM rule_packages WHERE package_id=? AND version=?",
                (package_id, version),
            ).fetchone()
        return row["status"] if row else None

    # ------------------------------------------------------------------- replays
    def save_replay(self, report: ReplayReport, observed_versions: Mapping[str, int] | None = None) -> str:
        candidate = RulePackage.from_dict(report.candidate_package)
        observed_versions = observed_versions or {}
        with self.transaction() as connection:
            if not connection.execute(
                "SELECT 1 FROM rule_packages WHERE package_id=? AND version=?",
                (candidate.package_id, candidate.version),
            ).fetchone():
                raise ContractError("candidate package must be registered before replay")
            if connection.execute("SELECT 1 FROM replay_runs WHERE replay_id=?",
                                  (report.replay_id,)).fetchone():
                return report.replay_id
            report_body = json.loads(canonical_json(report.as_dict()))
            stored_fingerprint = report_body.pop("fingerprint")
            if stable_hash(report_body) != stored_fingerprint:
                raise ContractError("replay report integrity check failed")
            report_body["fingerprint"] = stored_fingerprint
            report_json = canonical_json(report_body)
            connection.execute(
                "INSERT INTO replay_runs(replay_id,package_id,package_version,baseline_id,baseline_version,"
                "report_json,report_hash,label_hash,eligible,evidence_valid,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    report.replay_id,
                    candidate.package_id,
                    candidate.version,
                    report.baseline_package["package_id"],
                    report.baseline_package["version"],
                    report_json,
                    report.fingerprint,
                    report.label_hash,
                    1 if report.eligibility.eligible else 0,
                    1,
                    utc_now(),
                ),
            )
            for record_id, fingerprint in sorted(report.observation_fingerprints.items()):
                connection.execute(
                    "INSERT INTO replay_observations(replay_id,record_id,observation_fingerprint,observed_version)"
                    " VALUES(?,?,?,?)",
                    (report.replay_id, record_id, fingerprint, observed_versions.get(record_id)),
                )
            self.append_event(
                connection,
                "replay.saved",
                report.replay_id,
                1,
                {
                    "replay_id": report.replay_id,
                    "package": candidate.basis(),
                    "eligible": report.eligibility.eligible,
                    "report_hash": report.fingerprint,
                },
            )
        return report.replay_id

    def get_replay(self, replay_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM replay_runs WHERE replay_id=?",
                                     (replay_id,)).fetchone()
        if not row:
            return None
        return dict(row) | {"report": json.loads(row["report_json"])}

    def replay_evidence(self, replay_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM replay_observations WHERE replay_id=? ORDER BY record_id",
                (replay_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def replay_is_invalidated(self, replay_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM replay_observations WHERE replay_id=? AND invalidated_at IS NOT NULL",
                (replay_id,),
            ).fetchone()
        return int(row[0]) > 0

    # ------------------------------------------------------------------- reviews
    def submit_for_review(
        self,
        package_id: str,
        package_version: int,
        replay_id: str,
        decided_by: str,
        rationale: str,
    ) -> str:
        package_id = identifier(package_id)
        decided_by = identifier(decided_by)
        rationale = " ".join(str(rationale or "").split())
        if not rationale:
            raise ContractError("review submission requires evidence-based rationale")
        with self.transaction() as connection:
            status = self._package_status_row(connection, package_id, package_version)
            if status not in REVIEWABLE_STATUSES:
                raise ContractError(f"package cannot enter review from status {status!r}")
            replay = connection.execute(
                "SELECT * FROM replay_runs WHERE replay_id=?", (replay_id,)
            ).fetchone()
            if not replay:
                raise ContractError("unknown replay evidence")
            if replay["package_id"] != package_id or replay["package_version"] != package_version:
                raise ContractError("replay evidence does not belong to this package")
            if not replay["eligible"]:
                raise ContractError("only evidence-backed eligible candidates can enter review")
            if replay["evidence_valid"] != 1 or self._replay_invalidated_row(connection, replay_id):
                raise ContractError("replay evidence has been invalidated by observation corrections")
            review_id = stable_hash(
                {"package_id": package_id, "package_version": package_version,
                 "replay_id": replay_id, "evidence_hash": replay["report_hash"]}
            )[:24]
            connection.execute(
                "INSERT OR IGNORE INTO candidate_reviews(review_id,package_id,package_version,replay_id,"
                "status,rationale,decided_by,evidence_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (review_id, package_id, package_version, replay_id, "submitted",
                 rationale, decided_by, replay["report_hash"], utc_now()),
            )
            self._set_package_status(connection, package_id, package_version, "in_review")
            self._history(connection, package_id, package_version, "submitted",
                          {"review_id": review_id, "replay_id": replay_id,
                           "rationale": rationale}, decided_by)
            self.append_event(connection, "review.submitted", review_id, 1,
                              {"package_id": package_id, "package_version": package_version,
                               "replay_id": replay_id})
        return review_id

    def decide_review(
        self,
        review_id: str,
        approve: bool,
        decided_by: str,
        rationale: str,
        live_repository: Any | None = None,
    ) -> dict[str, Any]:
        decided_by = identifier(decided_by)
        rationale = " ".join(str(rationale or "").split())
        if not rationale:
            raise ContractError("review decision requires rationale")
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM candidate_reviews WHERE review_id=?",
                                     (review_id,)).fetchone()
            if not row:
                raise ContractError("unknown review")
            if row["status"] != "submitted":
                raise ContractError(f"review already decided: {row['status']}")
            if self._replay_invalidated_row(connection, row["replay_id"]):
                raise ContractError("review blocked: replay evidence invalidated")
            new_status = "approved" if approve else "rejected"
            connection.execute(
                "UPDATE candidate_reviews SET status=?,decided_by=?,rationale=?,decided_at=?"
                " WHERE review_id=?",
                (new_status, decided_by, rationale, utc_now(), review_id),
            )
            self._set_package_status(connection, row["package_id"], row["package_version"], new_status)
            self._history(connection, row["package_id"], row["package_version"],
                          "approved" if approve else "rejected",
                          {"review_id": review_id, "rationale": rationale}, decided_by)
            self.append_event(connection, f"review.{new_status}", review_id, 1,
                              {"package_id": row["package_id"],
                               "package_version": row["package_version"]})
        return {"review_id": review_id, "status": new_status}

    def withdraw_candidate(self, package_id: str, package_version: int, actor: str, reason: str) -> None:
        actor = identifier(actor)
        reason = " ".join(str(reason or "").split())
        if not reason:
            raise ContractError("withdrawal requires a reason")
        with self.transaction() as connection:
            status = self._package_status_row(connection, package_id, package_version)
            if status not in ("candidate", "in_review", "approved", "rejected"):
                raise ContractError(f"package cannot be withdrawn from status {status!r}")
            connection.execute(
                "UPDATE candidate_reviews SET status='withdrawn',decided_at=? WHERE package_id=?"
                " AND package_version=? AND status='submitted'",
                (utc_now(), package_id, package_version),
            )
            self._set_package_status(connection, package_id, package_version, "withdrawn")
            self._history(connection, package_id, package_version, "withdrawn",
                          {"reason": reason}, actor)
            self.append_event(connection, "package.withdrawn", package_id, package_version,
                              {"reason": reason})

    # ------------------------------------------------------------------ enabling
    def enable_package(
        self,
        package_id: str,
        package_version: int,
        live_repository: Any,
        actor: str,
    ) -> dict[str, Any]:
        """Enable after re-verifying observations and rule versions against live data."""
        actor = identifier(actor)
        with self.transaction() as connection:
            status = self._package_status_row(connection, package_id, package_version)
            if status != "approved":
                raise ContractError(f"only approved packages can be enabled, current status: {status!r}")
            review = connection.execute(
                "SELECT * FROM candidate_reviews WHERE package_id=? AND package_version=? AND status='approved'",
                (package_id, package_version),
            ).fetchone()
            if not review:
                raise ContractError("approved review record missing")
            replay_id = review["replay_id"]
            if self._replay_invalidated_row(connection, replay_id):
                raise ContractError("enable blocked: replay evidence invalidated")
            self._verify_live_evidence(connection, replay_id, live_repository)
            fingerprint = connection.execute(
                "SELECT fingerprint FROM rule_packages WHERE package_id=? AND version=?",
                (package_id, package_version),
            ).fetchone()["fingerprint"]

            # Single active enabled package: supersede the previous one.
            connection.execute(
                "UPDATE enabled_rules SET superseded_at=? WHERE superseded_at IS NULL",
                (utc_now(),),
            )
            connection.execute(
                "UPDATE rule_packages SET status='superseded',updated_at=? WHERE status='enabled'",
                (utc_now(),),
            )
            connection.execute(
                "INSERT INTO enabled_rules(package_id,package_version,fingerprint,review_id,replay_id,enabled_at)"
                " VALUES(?,?,?,?,?,?)",
                (package_id, package_version, fingerprint, review["review_id"], replay_id, utc_now()),
            )
            self._set_package_status(connection, package_id, package_version, "enabled")
            self._history(connection, package_id, package_version, "enabled",
                          {"review_id": review["review_id"], "replay_id": replay_id}, actor)
            self.append_event(connection, "package.enabled", package_id, package_version,
                              {"fingerprint": fingerprint, "review_id": review["review_id"],
                               "replay_id": replay_id})
        return {"package_id": package_id, "version": package_version,
                "review_id": review["review_id"], "replay_id": replay_id}

    def _verify_live_evidence(
        self,
        connection: sqlite3.Connection,
        replay_id: str,
        live_repository: Any,
    ) -> None:
        """Read-only check: every replay observation must still match live data."""
        evidence_rows = connection.execute(
            "SELECT record_id,observation_fingerprint,observed_version FROM replay_observations"
            " WHERE replay_id=?",
            (replay_id,),
        ).fetchall()
        for row in evidence_rows:
            live = live_repository.get_record(row["record_id"])
            if live is None:
                raise ContractError(
                    f"enable blocked: observation {row['record_id']} no longer exists live"
                )
            if live.fingerprint != row["observation_fingerprint"]:
                raise ContractError(
                    f"enable blocked: observation {row['record_id']} was corrected after trial"
                )
            if row["observed_version"] is not None and live.version != row["observed_version"]:
                raise ContractError(
                    f"enable blocked: observation {row['record_id']} version changed"
                )
        # Rule version check: without an enabled package the live engine must still
        # serve the production baseline; a foreign rule basis means control drifted.
        enabled = self.active_enabled_row(connection)
        if enabled is None and hasattr(live_repository, "active_rule_basis"):
            live_baseline = live_repository.active_rule_basis()
            if live_baseline and live_baseline.get("package_id") not in (None, BASELINE_PACKAGE_ID):
                raise ContractError("enable blocked: live rule basis changed outside trial control")

    def active_enabled_row(self, connection: sqlite3.Connection | None = None) -> sqlite3.Row | None:
        owns = connection is None
        connection = connection or self.connect()
        try:
            return connection.execute(
                "SELECT * FROM enabled_rules WHERE superseded_at IS NULL ORDER BY enabled_at DESC LIMIT 1"
            ).fetchone()
        finally:
            if owns:
                connection.close()

    def active_basis(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = self.active_enabled_row(connection)
            if not row:
                return None
            return {"package_id": row["package_id"], "version": row["package_version"],
                    "fingerprint": row["fingerprint"], "review_id": row["review_id"],
                    "replay_id": row["replay_id"], "enabled_at": row["enabled_at"]}

    def active_package(self) -> RulePackage | None:
        basis = self.active_basis()
        if not basis:
            return None
        return self.get_package(basis["package_id"], basis["version"])

    # ------------------------------------------------------------- corrections
    def record_observation_correction(
        self,
        record_id: str,
        old_fingerprint: str,
        new_fingerprint: str,
        observed_version: int,
        reason: str,
    ) -> list[str]:
        """Mark every replay that relied on the corrected observation as invalid."""
        record_id = identifier(record_id)
        reason = " ".join(str(reason or "").split())
        if not reason:
            raise ContractError("correction requires a reason")
        if old_fingerprint == new_fingerprint:
            raise ContractError("correction requires a changed fingerprint")
        invalidated_replays: list[str] = []
        with self.transaction() as connection:
            correction_id = stable_hash(
                {"record_id": record_id, "old_fingerprint": old_fingerprint,
                 "new_fingerprint": new_fingerprint, "observed_version": observed_version,
                 "reason": reason, "at": utc_now()}
            )[:24]
            connection.execute(
                "INSERT OR IGNORE INTO observation_corrections(correction_id,record_id,old_fingerprint,"
                "new_fingerprint,observed_version,reason,recorded_at) VALUES(?,?,?,?,?,?,?)",
                (correction_id, record_id, old_fingerprint, new_fingerprint,
                 observed_version, reason, utc_now()),
            )
            rows = connection.execute(
                "SELECT replay_id FROM replay_observations WHERE record_id=?"
                " AND observation_fingerprint=? AND invalidated_at IS NULL",
                (record_id, old_fingerprint),
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE replay_observations SET invalidated_at=? WHERE replay_id=? AND record_id=?",
                    (utc_now(), row["replay_id"], record_id),
                )
                connection.execute(
                    "UPDATE replay_runs SET evidence_valid=0 WHERE replay_id=?", (row["replay_id"],)
                )
                invalidated_replays.append(row["replay_id"])
                self.append_event(connection, "replay.invalidated", row["replay_id"], 1,
                                  {"record_id": record_id, "correction_id": correction_id,
                                   "reason": reason})
            self.append_event(connection, "observation.corrected", record_id, observed_version,
                              {"correction_id": correction_id, "old_fingerprint": old_fingerprint,
                               "new_fingerprint": new_fingerprint, "reason": reason,
                               "invalidated_replays": invalidated_replays})
        return invalidated_replays

    def revoke_invalid_enabled(
        self,
        live_repository: Any,
        actor: str,
        reason: str,
    ) -> dict[str, Any] | None:
        """Withdraw an enabled candidate whose trial conclusion was overturned."""
        actor = identifier(actor)
        reason = " ".join(str(reason or "").split())
        if not reason:
            raise ContractError("revocation requires a reason")
        with self.transaction() as connection:
            enabled = self.active_enabled_row(connection)
            if not enabled:
                return None
            invalidated = self._replay_invalidated_row(connection, enabled["replay_id"])
            live_mismatch = False
            try:
                self._verify_live_evidence(connection, enabled["replay_id"], live_repository)
            except ContractError:
                live_mismatch = True
            if not invalidated and not live_mismatch:
                return None
            connection.execute(
                "UPDATE enabled_rules SET superseded_at=? WHERE package_id=? AND package_version=?",
                (utc_now(), enabled["package_id"], enabled["package_version"]),
            )
            self._set_package_status(connection, enabled["package_id"],
                                     enabled["package_version"], "revoked")
            connection.execute(
                "UPDATE candidate_reviews SET status='revoked',decided_at=? WHERE review_id=?",
                (utc_now(), enabled["review_id"]),
            )
            self._history(connection, enabled["package_id"], enabled["package_version"],
                          "revoked",
                          {"reason": reason, "invalidated_evidence": invalidated,
                           "live_mismatch": live_mismatch,
                           "replay_id": enabled["replay_id"]}, actor)
            self.append_event(connection, "package.revoked", enabled["package_id"],
                              enabled["package_version"],
                              {"reason": reason, "replay_id": enabled["replay_id"],
                               "invalidated_evidence": invalidated,
                               "live_mismatch": live_mismatch})
        return {"package_id": enabled["package_id"], "version": enabled["package_version"],
                "reason": reason, "invalidated_evidence": invalidated,
                "live_mismatch": live_mismatch}

    # ------------------------------------------------------------------- queries
    def list_reviews(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM candidate_reviews"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status=?"
            params = (status,)
        query += " ORDER BY created_at"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def review_history(self, package_id: str, package_version: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM review_history WHERE package_id=? AND package_version=?"
                " ORDER BY history_id",
                (package_id, package_version),
            ).fetchall()
        return [dict(row) | {"detail": json.loads(row["detail_json"])} for row in rows]

    def list_corrections(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM observation_corrections ORDER BY recorded_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def verify_trial_chain(self) -> list[str]:
        errors: list[str] = []
        previous = "0" * 64
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM trial_events ORDER BY event_id").fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            expected = stable_hash(
                {
                    "event_type": row["event_type"],
                    "aggregate_id": row["aggregate_id"],
                    "aggregate_version": row["aggregate_version"],
                    "payload": payload,
                    "previous_hash": row["previous_hash"],
                    "created_at": row["created_at"],
                }
            )
            if row["previous_hash"] != previous:
                errors.append(f"trial event {row['event_id']} previous hash mismatch")
            if row["event_hash"] != expected:
                errors.append(f"trial event {row['event_id']} content hash mismatch")
            previous = row["event_hash"]
        return errors

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _package_status_row(connection: sqlite3.Connection, package_id: str,
                            package_version: int) -> str:
        row = connection.execute(
            "SELECT status FROM rule_packages WHERE package_id=? AND version=?",
            (package_id, package_version),
        ).fetchone()
        if not row:
            raise ContractError("unknown rule package")
        return row["status"]

    @staticmethod
    def _set_package_status(connection: sqlite3.Connection, package_id: str,
                            package_version: int, status: str) -> None:
        changed = connection.execute(
            "UPDATE rule_packages SET status=?,updated_at=? WHERE package_id=? AND version=?",
            (status, utc_now(), package_id, package_version),
        ).rowcount
        if changed != 1:
            raise ContractError("rule package status update failed")

    @staticmethod
    def _replay_invalidated_row(connection: sqlite3.Connection, replay_id: str) -> bool:
        row = connection.execute(
            "SELECT COUNT(*) FROM replay_observations WHERE replay_id=? AND invalidated_at IS NOT NULL",
            (replay_id,),
        ).fetchone()
        return int(row[0]) > 0
