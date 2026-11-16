from __future__ import annotations

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
