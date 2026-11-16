from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from basin_warning.observations.hydro_event import ContractError, DomainRecord
from basin_warning.replay.timeline_store import Repository


class NotificationLedgerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "basin.sqlite3"
        self.repository = Repository(self.database)
        self.repository.save_record(DomainRecord("observation-a", {"station_id": "station-a"}))
        self.repository.register_reach("downstream", None, 0.0)
        self.repository.register_reach("upstream", "downstream", 4.0)
        self.repository.assign_station("station-a", "upstream")

    def test_notice_retains_observation_version_and_delivery_fact(self):
        first = self.repository.issue_notice("notice-a", "upstream", "observation-a", 1)
        self.assertEqual(self.repository.issue_notice("notice-a", "upstream", "observation-a", 1), first)
        self.repository.update_notice("notice-a", "delivered")
        self.repository.update_notice("notice-a", "acknowledged")
        with self.assertRaisesRegex(ContractError, "invalid notice"):
            self.repository.update_notice("notice-a", "cancelled")
        with self.assertRaisesRegex(ContractError, "cannot be reassigned"):
            self.repository.issue_notice("notice-a", "downstream", "observation-a", 1)
        self.assertEqual(Repository(self.database).reach_notices("upstream")[0]["status"], "acknowledged")
        self.assertEqual(self.repository.reach_notices("downstream"), [])

    def test_pending_can_cancel_and_unknown_observation_cannot_notify(self):
        self.repository.issue_notice("pending", "upstream", "observation-a", 1)
        self.assertEqual(self.repository.update_notice("pending", "cancelled")["status"], "cancelled")
        with self.assertRaisesRegex(ContractError, "unknown"):
            self.repository.issue_notice("missing", "upstream", "observation-a", 2)

    def test_notice_carries_and_preserves_rule_basis(self):
        basis = {"package_id": "candidate-balanced", "version": 1,
                 "fingerprint": "a" * 64}
        self.repository.issue_notice(
            "notice-basis", "upstream", "observation-a", 1, rule_basis=basis
        )
        stored = self.repository.reach_notices("upstream")
        notice = next(row for row in stored if row["notice_id"] == "notice-basis")
        self.assertEqual(json.loads(notice["rule_basis_json"]), basis)
        # Re-issuing the same notice is idempotent and keeps the original basis.
        again = self.repository.issue_notice(
            "notice-basis", "upstream", "observation-a", 1, rule_basis=basis
        )
        self.assertEqual(json.loads(again["rule_basis_json"]), basis)
        self.repository.update_notice("notice-basis", "delivered")
        delivered = next(row for row in self.repository.reach_notices("upstream")
                         if row["notice_id"] == "notice-basis")
        self.assertEqual(delivered["status"], "delivered")
        self.assertEqual(json.loads(delivered["rule_basis_json"]), basis)

    def test_notice_without_basis_defaults_to_baseline(self):
        self.repository.issue_notice("notice-default", "upstream", "observation-a", 1)
        notice = next(row for row in self.repository.reach_notices("upstream")
                      if row["notice_id"] == "notice-default")
        self.assertEqual(
            json.loads(notice["rule_basis_json"])["package_id"], "baseline-rule-package"
        )
