"""Shared helpers for shadow-trial tests.

Builds a deterministic eligible candidate from numeric acceptance observations:
relax every failing rule threshold and guard floor, then raise the approve
threshold so that, against labels aligned to the remaining approve set, the
candidate cuts false positives without introducing misses.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from basin_warning.alerts.escalation import GUARDS, decide
from basin_warning.fusion.conflict_resolution import RULES
from basin_warning.observations.hydro_event import records_from_fixture
from basin_warning.replay.rule_package import RulePackage

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "acceptance.json"
_GUARD_PATTERN = re.compile(r"^(guard_.+_\d+)$")


def numeric_records():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for index, record in enumerate(fixture["records"]):
        record["occurred_at"] = f"2026-11-01T{index:02d}:00:00+00:00"
    return records_from_fixture(fixture)


def _relaxing_overrides(records):
    overrides = {}
    for record in records:
        for rule in RULES:
            result = rule(record, {})
            if not result.passed:
                evidence = result.evidence
                overrides.setdefault(
                    f"{result.code}_threshold",
                    1000.0
                    if evidence.get("adjusted", 0) >= evidence.get("threshold", 0)
                    else 0.0,
                )
    for guard in GUARDS:
        overrides[_GUARD_PATTERN.match(guard.__name__).group(1) + "_floor"] = 0.0
    return overrides


def build_eligible_candidate(records, labels, package_id="candidate-good",
                             approve_threshold=0.78):
    """Return a candidate that is eligible against the supplied labels.

    Labels must mark the approve-set at ``approve_threshold`` as real events so
    that recall stays at 1.0 while non-event alerts are removed.
    """
    overrides = _relaxing_overrides(records)
    candidate = RulePackage(
        package_id,
        1,
        overrides | {"approve_threshold": approve_threshold},
        alert_outcomes=("approve",),
    )
    return candidate


def approve_set(records, candidate_overrides, approve_threshold):
    return {
        record.record_id
        for record in records
        if decide(record, candidate_overrides | {"approve_threshold": approve_threshold}).outcome
        == "approve"
    }


def labels_for_approve_set(records, event_ids):
    return {
        record.record_id: {
            "actual_event": record.record_id in event_ids,
            "event_type": "flood" if index % 2 else "storm",
            "event_time": "2026-11-16T12:00:00+00:00",
        }
        for index, record in enumerate(records)
    }
