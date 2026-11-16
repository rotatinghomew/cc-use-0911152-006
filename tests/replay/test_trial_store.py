from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from basin_warning.observations.hydro_event import ContractError
from basin_warning.replay.replay_engine import replay_candidate
from basin_warning.replay.rule_package import RulePackage, baseline_package
from basin_warning.replay.trial_store import TrialStore

from tests.replay._helpers import (
    approve_set,
    build_eligible_candidate,
    labels_for_approve_set,
    numeric_records,
)


class FakeLiveRepository:
    """Minimal read-only stand-in for the live Repository during enablement."""

    def __init__(self, records):
        self._records = {record.record_id: record for record in records}

    def get_record(self, record_id):
        return self._records.get(record_id)

    def active_rule_basis(self):
        return baseline_package().basis()


class TrialStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TrialStore(Path(self.temp.name) / "trial.sqlite3")
        self.records = numeric_records()
        self.versions = {record.record_id: record.version for record in self.records}

        self.candidate = RulePackage("candidate-a", 1, {"approve_threshold": 0.4})
        # A deterministically eligible candidate against aligned labels.
        good = build_eligible_candidate(self.records, None)
        self.good_overrides = dict(good.context_overrides)
        event_ids = approve_set(self.records, self.good_overrides, 0.78)
        self.labels = labels_for_approve_set(self.records, event_ids)
        self.good = RulePackage(
            "candidate-good", 1, self.good_overrides, alert_outcomes=("approve",)
        )
        report = replay_candidate(self.records, self.labels, self.good)
        self.assertTrue(report.eligibility.eligible, report.eligibility.blocking_reasons)
        self.good_report = report

    def test_package_registration_is_idempotent_and_immutable(self):
        first = self.store.register_package(self.candidate)
        second = self.store.register_package(self.candidate)
        self.assertEqual(first, second)
        changed = RulePackage("candidate-a", 1, {"approve_threshold": 0.5})
        with self.assertRaisesRegex(ContractError, "content cannot change"):
            self.store.register_package(changed)
        self.assertEqual(self.store.package_status("candidate-a", 1), "candidate")

    def test_replay_requires_registered_package(self):
        with self.assertRaisesRegex(ContractError, "must be registered"):
            self.store.save_replay(self.good_report)

    def test_replay_round_trip_and_evidence_pinning(self):
        self.store.register_package(self.good)
        replay_id = self.store.save_replay(self.good_report, observed_versions=self.versions)
        stored = self.store.get_replay(replay_id)
        self.assertEqual(stored["report_hash"], self.good_report.fingerprint)
        evidence = self.store.replay_evidence(replay_id)
        self.assertEqual(len(evidence), len(self.records))
        self.assertTrue(all(row["invalidated_at"] is None for row in evidence))
        self.assertEqual(self.store.verify_trial_chain(), [])

    def test_ineligible_candidate_cannot_enter_review(self):
        silent = RulePackage(
            "silent", 1,
            {"approve_threshold": 99.0, "review_threshold": 99.0},
            alert_outcomes=("approve",),
        )
        report = replay_candidate(self.records, self.labels, silent)
        self.assertFalse(report.eligibility.eligible)
        self.store.register_package(silent)
        self.store.save_replay(report)
        with self.assertRaisesRegex(ContractError, "eligible candidates"):
            self.store.submit_for_review("silent", 1, report.replay_id, "officer", "try anyway")

    def test_review_requires_rationale(self):
        self.store.register_package(self.good)
        replay_id = self.store.save_replay(self.good_report, observed_versions=self.versions)
        with self.assertRaisesRegex(ContractError, "rationale"):
            self.store.submit_for_review("candidate-good", 1, replay_id, "officer", "  ")

    def _approved_review(self):
        self.store.register_package(self.good)
        replay_id = self.store.save_replay(self.good_report, observed_versions=self.versions)
        review_id = self.store.submit_for_review(
            "candidate-good", 1, replay_id, "officer-li", "evidence supports enablement"
        )
        self.store.decide_review(
            review_id, True, "board-wang", "approved", FakeLiveRepository(self.records)
        )
        return review_id, replay_id

    def test_full_review_and_enable_lifecycle_with_live_verification(self):
        review_id, _ = self._approved_review()
        enabled = self.store.enable_package(
            "candidate-good", 1, FakeLiveRepository(self.records), "commander-zhao"
        )
        self.assertEqual(enabled["review_id"], review_id)
        basis = self.store.active_basis()
        self.assertEqual(basis["package_id"], "candidate-good")
        self.assertEqual(self.store.active_package().fingerprint, self.good.fingerprint)
        self.assertEqual(self.store.package_status("candidate-good", 1), "enabled")

    def test_enable_blocked_when_live_observation_changed(self):
        self._approved_review()
        changed = [record.with_payload({"rainfall_mm": 4242.0}) if index == 0 else record
                   for index, record in enumerate(self.records)]
        with self.assertRaisesRegex(ContractError, "was corrected after trial"):
            self.store.enable_package(
                "candidate-good", 1, FakeLiveRepository(changed), "zhao"
            )

    def test_enable_blocked_when_live_observation_disappears(self):
        self._approved_review()
        reduced = FakeLiveRepository(self.records[1:])
        with self.assertRaisesRegex(ContractError, "no longer exists live"):
            self.store.enable_package("candidate-good", 1, reduced, "zhao")

    def test_enable_blocked_when_evidence_was_invalidated(self):
        self._approved_review()
        target = self.records[0]
        corrected = target.with_payload({"rainfall_mm": 777.0})
        self.store.record_observation_correction(
            target.record_id, target.fingerprint, corrected.fingerprint,
            corrected.version, "gauge recalibration"
        )
        with self.assertRaisesRegex(ContractError, "evidence invalidated"):
            self.store.enable_package(
                "candidate-good", 1, FakeLiveRepository(self.records), "zhao"
            )

    def test_observation_correction_invalidates_replay_and_revokes_enabled(self):
        _, replay_id = self._approved_review()
        self.store.enable_package(
            "candidate-good", 1, FakeLiveRepository(self.records), "zhao"
        )
        target = self.records[0]
        corrected = target.with_payload({"rainfall_mm": 777.0})
        invalidated = self.store.record_observation_correction(
            target.record_id, target.fingerprint, corrected.fingerprint,
            corrected.version, "gauge recalibration"
        )
        self.assertIn(replay_id, invalidated)
        self.assertTrue(self.store.replay_is_invalidated(replay_id))
        # A repeat correction against the already-superseded fingerprint is a no-op.
        again = self.store.record_observation_correction(
            target.record_id, target.fingerprint, corrected.fingerprint,
            corrected.version, "duplicate"
        )
        self.assertEqual(again, [])
        revocation = self.store.revoke_invalid_enabled(
            FakeLiveRepository([corrected] + self.records[1:]), "system", "evidence overturned"
        )
        self.assertIsNotNone(revocation)
        self.assertEqual(revocation["package_id"], "candidate-good")
        self.assertTrue(revocation["invalidated_evidence"])
        self.assertIsNone(self.store.active_basis())
        self.assertEqual(self.store.package_status("candidate-good", 1), "revoked")
        history = self.store.review_history("candidate-good", 1)
        actions = [row["action"] for row in history]
        self.assertEqual(actions, ["registered", "submitted", "approved", "enabled", "revoked"])
        # The review history retains the correction reason behind the withdrawal.
        correction_rows = self.store.list_corrections()
        self.assertTrue(
            any("gauge recalibration" in row["reason"] for row in correction_rows)
        )
        revoked_detail = next(row["detail"] for row in history if row["action"] == "revoked")
        self.assertEqual(revoked_detail["replay_id"], replay_id)

    def test_revoke_is_noop_when_evidence_still_valid(self):
        self._approved_review()
        self.store.enable_package(
            "candidate-good", 1, FakeLiveRepository(self.records), "zhao"
        )
        self.assertIsNone(
            self.store.revoke_invalid_enabled(
                FakeLiveRepository(self.records), "system", "nothing wrong"
            )
        )
        self.assertIsNotNone(self.store.active_basis())

    def test_revoked_package_cannot_be_re_enabled(self):
        self._approved_review()
        self.store.enable_package(
            "candidate-good", 1, FakeLiveRepository(self.records), "zhao"
        )
        corrected = self.records[0].with_payload({"rainfall_mm": 777.0})
        self.store.record_observation_correction(
            self.records[0].record_id, self.records[0].fingerprint,
            corrected.fingerprint, corrected.version, "correction"
        )
        self.store.revoke_invalid_enabled(
            FakeLiveRepository([corrected] + self.records[1:]), "system", "overturned"
        )
        with self.assertRaisesRegex(ContractError, "only approved"):
            self.store.enable_package(
                "candidate-good", 1, FakeLiveRepository(self.records), "zhao"
            )

    def test_rejected_review_cannot_be_enabled(self):
        self.store.register_package(self.good)
        replay_id = self.store.save_replay(self.good_report, observed_versions=self.versions)
        review_id = self.store.submit_for_review(
            "candidate-good", 1, replay_id, "li", "submitted"
        )
        self.store.decide_review(review_id, False, "wang", "rejected after debate",
                                 FakeLiveRepository(self.records))
        with self.assertRaisesRegex(ContractError, "only approved"):
            self.store.enable_package(
                "candidate-good", 1, FakeLiveRepository(self.records), "zhao"
            )

    def test_decided_review_is_terminal(self):
        review_id, _ = self._approved_review()
        with self.assertRaisesRegex(ContractError, "already decided"):
            self.store.decide_review(review_id, False, "wang", "again",
                                     FakeLiveRepository(self.records))

    def test_withdrawal_removes_candidate_and_records_reason(self):
        self.store.register_package(self.candidate)
        self.store.withdraw_candidate("candidate-a", 1, "li", "superseded approach")
        self.assertEqual(self.store.package_status("candidate-a", 1), "withdrawn")
        history = self.store.review_history("candidate-a", 1)
        self.assertEqual(history[-1]["action"], "withdrawn")
        self.assertEqual(history[-1]["detail"]["reason"], "superseded approach")

    def test_withdrawal_requires_reason(self):
        self.store.register_package(self.candidate)
        with self.assertRaisesRegex(ContractError, "withdrawal requires a reason"):
            self.store.withdraw_candidate("candidate-a", 1, "li", " ")

    def test_correction_requires_changed_fingerprint(self):
        with self.assertRaisesRegex(ContractError, "changed fingerprint"):
            self.store.record_observation_correction("hazard-001", "same", "same", 1, "no-op")

    def test_chain_detects_tampering(self):
        self.store.register_package(self.candidate)
        self.assertEqual(self.store.verify_trial_chain(), [])
        with sqlite3.connect(self.store.database) as connection:
            connection.execute("UPDATE trial_events SET payload_json='{}' WHERE event_id=1")
        self.assertTrue(self.store.verify_trial_chain())

    def test_list_reviews_filters_by_status(self):
        self._approved_review()
        approved = self.store.list_reviews("approved")
        self.assertEqual(len(approved), 1)
        self.assertEqual(self.store.list_reviews("submitted"), [])


if __name__ == "__main__":
    unittest.main()
