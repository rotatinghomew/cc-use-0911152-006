from __future__ import annotations

import unittest

from basin_warning.observations.hydro_event import ContractError, DomainRecord
from basin_warning.replay.replay_engine import (
    Label,
    TrialPolicy,
    normalize_labels,
    replay_candidate,
    replay_portfolio,
    select_evidence_backed,
    station_of,
)
from basin_warning.replay.rule_package import RulePackage

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


def boolean_labels(records, event_indices):
    return {
        record.record_id: {
            "actual_event": index in event_indices,
            "event_type": "flood" if index % 2 else "storm",
            "event_time": "2026-11-02T00:00:00+00:00",
        }
        for index, record in enumerate(records)
    }


class LabelTests(unittest.TestCase):
    def test_labels_must_cover_every_record(self):
        records = [make_record(1), make_record(2)]
        with self.assertRaisesRegex(ContractError, "missing ground-truth"):
            normalize_labels(records, {records[0].record_id: True})

    def test_unknown_record_label_rejected(self):
        records = [make_record(1)]
        with self.assertRaisesRegex(ContractError, "unknown record"):
            normalize_labels(records, {records[0].record_id: True, "ghost": False})

    def test_boolean_and_object_labels_equivalent(self):
        records = [make_record(1)]
        labels = normalize_labels(records, {records[0].record_id: True})
        self.assertIsInstance(labels[records[0].record_id], Label)
        self.assertTrue(labels[records[0].record_id].actual_event)

    def test_station_fallback(self):
        record = DomainRecord("h", {"rainfall_mm": 1.0})
        self.assertEqual(station_of(record), "unknown-station")


class ReplayDeterminismTests(unittest.TestCase):
    def setUp(self):
        self.records = [make_record(seed) for seed in range(1, 6)]
        self.labels = boolean_labels(self.records, {0, 2})

    def test_replay_is_deterministic_and_fingerprinted(self):
        candidate = RulePackage("cand", 1, {"approve_threshold": 0.99})
        first = replay_candidate(self.records, self.labels, candidate)
        second = replay_candidate(self.records, self.labels, candidate)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.replay_id, second.replay_id)
        self.assertEqual(len(first.observation_fingerprints), len(self.records))

    def test_candidate_must_differ_from_baseline(self):
        from basin_warning.replay.rule_package import baseline_package
        with self.assertRaisesRegex(ContractError, "differ from the baseline"):
            replay_candidate(self.records, self.labels, baseline_package())

    def test_group_breakdowns_cover_every_station_and_type(self):
        candidate = RulePackage("cand", 1, {"review_threshold": 0.01})
        report = replay_candidate(self.records, self.labels, candidate)
        station_values = {group.group_value for group in report.station_comparisons}
        type_values = {group.group_value for group in report.event_type_comparisons}
        self.assertEqual(station_values, {station_of(record) for record in self.records})
        self.assertEqual(type_values, {"flood", "storm"})

    def test_confusion_counts_are_consistent(self):
        candidate = RulePackage("cand", 1, {"approve_threshold": 0.99,
                                            "review_threshold": 0.99})
        report = replay_candidate(self.records, self.labels, candidate)
        metrics = report.candidate_metrics
        self.assertEqual(
            metrics.true_positive + metrics.false_positive
            + metrics.true_negative + metrics.false_negative,
            metrics.total,
        )
        self.assertEqual(metrics.alert_count, metrics.true_positive + metrics.false_positive)


class EligibilityGateTests(unittest.TestCase):
    def setUp(self):
        self.records = [make_record(seed) for seed in range(1, 9)]

    def test_false_alarm_only_candidate_is_never_selected(self):
        # A package that silences everything has the fewest false alarms but
        # misses every real event.
        labels = boolean_labels(self.records, {1, 4})
        silent = RulePackage("silent", 1,
                             {"approve_threshold": 99.0, "review_threshold": 99.0},
                             alert_outcomes=("approve",))
        report = replay_candidate(self.records, labels, silent)
        self.assertEqual(report.candidate_metrics.false_positive, 0)
        self.assertFalse(report.eligibility.eligible)
        self.assertTrue(
            any("miss" in reason for reason in report.eligibility.blocking_reasons)
        )
        self.assertIsNone(select_evidence_backed([report]))

    def test_candidate_with_recall_regression_blocked_even_with_fewer_false_alarms(self):
        labels = boolean_labels(self.records, {0, 1, 2})
        candidate = RulePackage("risky", 1,
                                {"approve_threshold": 0.99, "review_threshold": 0.99},
                                alert_outcomes=("approve",))
        report = replay_candidate(self.records, labels, candidate)
        reasons = " ".join(report.eligibility.blocking_reasons)
        self.assertIn("recall regresses", reasons)
        self.assertFalse(report.eligibility.eligible)

    def test_portfolio_prefers_eligible_candidate_over_quiet_one(self):
        labels = boolean_labels(self.records, {3, 5})
        silent = RulePackage("silent", 1,
                             {"approve_threshold": 99.0, "review_threshold": 99.0},
                             alert_outcomes=("approve",))
        # A policy that allows everything still cannot rescue a package that
        # fails the recall checks when those checks are required.
        relaxed_policy = TrialPolicy(min_false_positive_reduction=0)
        reports = replay_portfolio(self.records, labels, [silent], policy=relaxed_policy)
        self.assertFalse(reports[0].eligibility.eligible)
        self.assertIsNone(select_evidence_backed(reports))

    def test_scoped_candidate_only_compares_in_scope_evidence(self):
        labels = boolean_labels(self.records, {0})
        target_station = station_of(self.records[0])
        scoped = RulePackage(
            "scoped",
            1,
            {"approve_threshold": 0.99},
            scope={"station_ids": [target_station]},
        )
        report = replay_candidate(self.records, labels, scoped)
        in_scope = [outcome for outcome in report.candidate_outcomes
                    if outcome.station_id == target_station]
        self.assertTrue(in_scope)
        self.assertTrue(
            all(outcome.station_id == target_station for outcome in report.candidate_outcomes)
        )
        # Baseline comparison uses the same scoped subset, so totals match.
        self.assertEqual(report.baseline_metrics.total, report.candidate_metrics.total)

    def test_empty_scope_is_rejected(self):
        labels = boolean_labels(self.records, {0})
        scoped = RulePackage("nowhere", 1, scope={"station_ids": ["station-zzz"]})
        with self.assertRaisesRegex(ContractError, "matches no labelled"):
            replay_candidate(self.records, labels, scoped)


class RuleContributionTests(unittest.TestCase):
    def test_each_flip_is_classified_with_benefit_or_cost(self):
        records = [make_record(seed) for seed in range(1, 6)]
        labels = boolean_labels(records, {0})
        candidate = RulePackage("cand", 1, {"review_threshold": 0.01,
                                            "approve_threshold": 0.01})
        report = replay_candidate(records, labels, candidate)
        for flip in report.rule_flips:
            self.assertIn(flip.impact,
                          {"fixed_false_alarm", "new_miss", "caught_event",
                           "new_false_alarm", "neutral"})
        for contribution in report.rule_contributions:
            self.assertGreaterEqual(contribution.benefit, 0)
            self.assertGreaterEqual(contribution.cost, 0)
            self.assertEqual(
                contribution.flips,
                contribution.fixed_false_alarms + contribution.new_misses
                + contribution.caught_events + contribution.new_false_alarms,
            )


if __name__ == "__main__":
    unittest.main()
