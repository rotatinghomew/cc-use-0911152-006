from __future__ import annotations

import unittest

from basin_warning.observations.hydro_event import ContractError
from basin_warning.replay.rule_package import (
    BASELINE_PACKAGE_ID,
    RulePackage,
    baseline_package,
    package_from_json_text,
)


class RulePackageTests(unittest.TestCase):
    def test_baseline_is_empty_and_fingerprinted(self):
        baseline = baseline_package()
        self.assertEqual(baseline.package_id, BASELINE_PACKAGE_ID)
        self.assertEqual(baseline.context_overrides, {})
        self.assertEqual(len(baseline.fingerprint), 64)
        self.assertEqual(baseline.basis()["package_id"], BASELINE_PACKAGE_ID)

    def test_immutable_identity_and_content_fingerprint(self):
        left = RulePackage("candidate-a", 2, {"approve_threshold": 0.7})
        right = RulePackage("candidate-a", 2, {"approve_threshold": 0.7})
        different = RulePackage("candidate-a", 2, {"approve_threshold": 0.71})
        self.assertEqual(left.fingerprint, right.fingerprint)
        self.assertNotEqual(left.fingerprint, different.fingerprint)
        with self.assertRaises(Exception):
            left.version = 3  # type: ignore[misc]

    def test_unknown_tuning_key_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "unknown rule tuning key"):
            RulePackage("bad", 1, {"not_a_real_key": 1.0})

    def test_known_tuning_key_families_accepted(self):
        package = RulePackage(
            "tuned",
            1,
            {
                "check_flow_rate_presence_threshold": 2.0,
                "guard_ack_rate_miss_risk_12_floor": 0.4,
                "metric_lead_time_01_offset": 0.05,
                "miss_risk_weight": 0.9,
                "approve_threshold": 0.66,
            },
        )
        self.assertEqual(len(package.context_overrides), 5)

    def test_invalid_outcomes_and_version_rejected(self):
        with self.assertRaisesRegex(ContractError, "alert outcome"):
            RulePackage("bad", 1, {"approve_threshold": 0.5}, alert_outcomes=("explode",))
        with self.assertRaisesRegex(ContractError, "positive integer"):
            RulePackage("bad", 0)

    def test_scope_filters_station_and_event_type(self):
        package = RulePackage(
            "scoped",
            1,
            scope={"station_ids": ["station-1"], "event_types": ["flood"]},
        )
        self.assertTrue(package.applies_to("station-1", "flood"))
        self.assertFalse(package.applies_to("station-2", "flood"))
        self.assertFalse(package.applies_to("station-1", "storm"))
        fleet = RulePackage("fleet", 1)
        self.assertTrue(fleet.applies_to("any", "thing"))

    def test_json_round_trip(self):
        package = RulePackage("candidate-x", 3, {"review_threshold": 0.33},
                              alert_outcomes=("approve", "review"), description="round trip")
        restored = package_from_json_text(__import__("json").dumps(package.content))
        self.assertEqual(restored.fingerprint, package.fingerprint)
        self.assertEqual(restored.alert_outcomes, ("approve", "review"))


if __name__ == "__main__":
    unittest.main()
