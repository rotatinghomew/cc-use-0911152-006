from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from basin_warning.observations.hydro_event import DomainRecord
from basin_warning.replay.replay_engine import replay_candidate
from basin_warning.replay.rule_package import RulePackage
from basin_warning.replay.trial_report import export_replay_bundle, verify_replay_bundle

FIELDS = ['station_id', 'rainfall_mm', 'water_level_m', 'flow_rate', 'gate_opening',
          'forecast_horizon_h', 'sensor_age_min', 'quality_flag', 'upstream_delay',
          'population_exposure', 'delivery_channels', 'ack_rate']


def make_record(seed: int) -> DomainRecord:
    payload = {}
    for index, field in enumerate(FIELDS):
        selector = (seed + index) % 4
        if selector == 0:
            payload[field] = seed * 9.5 + index * 1.25
        elif selector == 1:
            payload[field] = f'{field}-{seed % 5}'
        elif selector == 2:
            payload[field] = (seed + index) / 10.0
        else:
            payload[field] = (seed + index) % 2 == 0
    return DomainRecord(f'hazard-{seed:03d}', payload, 'observing',
                        occurred_at='2026-11-01T00:00:00+00:00')


class TrialBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.records = [make_record(seed) for seed in range(1, 6)]
        self.labels = {
            record.record_id: {
                "actual_event": index in {0, 2},
                "event_type": "flood",
                "event_time": "2026-11-02T00:00:00+00:00",
            }
            for index, record in enumerate(self.records)
        }
        self.report = replay_candidate(
            self.records, self.labels, RulePackage("cand", 1, {"approve_threshold": 0.5})
        )

    def test_bundle_exports_and_verifies(self):
        output = Path(self.temp.name) / "bundle"
        manifest = export_replay_bundle(output, self.report)
        self.assertIn("replay-report.json", manifest["files"])
        self.assertEqual(verify_replay_bundle(output), [])

    def test_tampering_is_detected_for_each_artifact(self):
        output = Path(self.temp.name) / "bundle"
        export_replay_bundle(output, self.report)
        target = output / "rule-contributions.json"
        body = json.loads(target.read_text(encoding="utf-8"))
        body.append({"rule_code": "forged"})
        target.write_text(json.dumps(body), encoding="utf-8")
        errors = verify_replay_bundle(output)
        self.assertIn("rule-contributions.json hash mismatch", errors)

    def test_manifest_tampering_is_detected(self):
        output = Path(self.temp.name) / "bundle"
        export_replay_bundle(output, self.report)
        manifest_path = output / "trial-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = "rewritten"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertIn("trial manifest hash mismatch", verify_replay_bundle(output))

    def test_missing_bundle_reported(self):
        missing = Path(self.temp.name) / "absent"
        self.assertEqual(verify_replay_bundle(missing), ["trial-manifest.json is missing"])


if __name__ == "__main__":
    unittest.main()
