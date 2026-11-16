"""Deterministic historical replay and alternative-rule comparison.

The engine replays *frozen* historical observations through both the production
baseline rule package and candidate rule packages.  It never writes to the live
repository and never advances workflow state: the same DomainRecord is scored
under each package and the outcomes are compared against ground-truth labels.

Outputs explain, per station and per event type:
  * false alarms (false positives), misses (false negatives), correct alerts,
    correct silences, precision, recall, F1 and alert volume;
  * lead time retained for every correctly alerted event;
  * which individual rule/guard thresholds flipped each decision, i.e. the
    contribution of each changed rule together with its measured cost.

Candidate gating is deliberately multi-criterion: a package with the fewest
false alarms but worse recall cannot be selected.
"""
from __future__ import annotations

import statistics
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from basin_warning.alerts.escalation import GUARDS, decide
from basin_warning.forecast.risk_surface import grouped_metrics
from basin_warning.observations.hydro_event import (
    ContractError,
    DomainRecord,
    canonical_json,
    identifier,
    stable_hash,
)
from basin_warning.replay.rule_package import RulePackage, baseline_package

DEFAULT_EVENT_TYPE = "unclassified"
DEFAULT_STATION_FALLBACK = "unknown-station"


def _parse_event_time(value: str) -> datetime:
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"invalid event timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Label:
    """Ground truth for one historical observation."""

    record_id: str
    actual_event: bool
    event_type: str = DEFAULT_EVENT_TYPE
    event_time: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", identifier(self.record_id))
        object.__setattr__(self, "event_type", identifier(self.event_type or DEFAULT_EVENT_TYPE))
        if not isinstance(self.actual_event, bool):
            raise ContractError("label actual_event must be boolean")
        if self.event_time is not None:
            _parse_event_time(self.event_time)


def normalize_labels(
    records: Sequence[DomainRecord], raw_labels: Mapping[str, Any] | None
) -> dict[str, Label]:
    """Accept {"record_id": bool} or {"record_id": {...}} labels, all required."""
    record_ids = [record.record_id for record in records]
    missing = set(record_ids)
    labels: dict[str, Label] = {}
    if raw_labels is None:
        raise ContractError("replay requires ground-truth labels")
    if not isinstance(raw_labels, Mapping):
        raise ContractError("replay labels must be an object keyed by record_id")
    for record_id, entry in raw_labels.items():
        key = identifier(record_id)
        if key not in missing:
            raise ContractError(f"label references unknown record: {key}")
        if isinstance(entry, bool):
            labels[key] = Label(key, entry)
        elif isinstance(entry, Mapping):
            actual = entry.get("actual_event")
            if not isinstance(actual, bool):
                raise ContractError(f"label {key} requires boolean actual_event")
            labels[key] = Label(
                key,
                actual,
                str(entry.get("event_type") or DEFAULT_EVENT_TYPE),
                entry.get("event_time"),
            )
        else:
            raise ContractError(f"label {key} must be boolean or object")
        missing.discard(key)
    if missing:
        raise ContractError(f"missing ground-truth labels for: {', '.join(sorted(missing))}")
    return labels


def station_of(record: DomainRecord) -> str:
    value = record.payload.get("station_id")
    if value in (None, ""):
        return DEFAULT_STATION_FALLBACK
    return identifier(value)


@dataclass(frozen=True)
class RuleFlip:
    record_id: str
    station_id: str
    event_type: str
    rule_code: str
    kind: str  # 'rule' | 'guard'
    baseline_passed: bool
    candidate_passed: bool
    baseline_value: float | None
    candidate_value: float | None
    decision_changed: bool
    label_actual_event: bool
    impact: str  # 'fixed_false_alarm' | 'new_miss' | 'caught_event' | 'new_false_alarm' | 'neutral'

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "station_id": self.station_id,
            "event_type": self.event_type,
            "rule_code": self.rule_code,
            "kind": self.kind,
            "baseline_passed": self.baseline_passed,
            "candidate_passed": self.candidate_passed,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "decision_changed": self.decision_changed,
            "label_actual_event": self.label_actual_event,
            "impact": self.impact,
        }


@dataclass(frozen=True)
class PackageOutcome:
    record_id: str
    station_id: str
    event_type: str
    outcome: str
    alerted: bool
    score: float
    actual_event: bool
    confusion: str  # 'tp' | 'fp' | 'tn' | 'fn'
    lead_time_hours: float | None
    event_time: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "station_id": self.station_id,
            "event_type": self.event_type,
            "outcome": self.outcome,
            "alerted": self.alerted,
            "score": self.score,
            "actual_event": self.actual_event,
            "confusion": self.confusion,
            "lead_time_hours": self.lead_time_hours,
            "event_time": self.event_time,
        }


def _confusion(alerted: bool, actual_event: bool) -> str:
    if alerted and actual_event:
        return "tp"
    if alerted and not actual_event:
        return "fp"
    if not alerted and actual_event:
        return "fn"
    return "tn"


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


@dataclass(frozen=True)
class ConfusionMetrics:
    total: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    alert_count: int
    false_alarm_rate: float | None
    miss_rate: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    lead_time_hours: list[float]
    median_lead_time_hours: float | None
    minimum_lead_time_hours: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "true_negative": self.true_negative,
            "false_negative": self.false_negative,
            "alert_count": self.alert_count,
            "false_alarm_rate": self.false_alarm_rate,
            "miss_rate": self.miss_rate,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "lead_time_hours": self.lead_time_hours,
            "median_lead_time_hours": self.median_lead_time_hours,
            "minimum_lead_time_hours": self.minimum_lead_time_hours,
        }


def _metrics_from_outcomes(outcomes: Sequence[PackageOutcome]) -> ConfusionMetrics:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    leads: list[float] = []
    for item in outcomes:
        counts[item.confusion] += 1
        if item.confusion == "tp" and item.lead_time_hours is not None:
            leads.append(item.lead_time_hours)
    actual_positive = counts["tp"] + counts["fn"]
    actual_negative = counts["fp"] + counts["tn"]
    precision = _rate(counts["tp"], counts["tp"] + counts["fp"])
    recall = _rate(counts["tp"], actual_positive)
    f1 = (
        round(2 * precision * recall / (precision + recall), 6)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    return ConfusionMetrics(
        total=len(outcomes),
        true_positive=counts["tp"],
        false_positive=counts["fp"],
        true_negative=counts["tn"],
        false_negative=counts["fn"],
        alert_count=counts["tp"] + counts["fp"],
        false_alarm_rate=_rate(counts["fp"], actual_negative),
        miss_rate=_rate(counts["fn"], actual_positive),
        precision=precision,
        recall=recall,
        f1=f1,
        lead_time_hours=[round(value, 6) for value in leads],
        median_lead_time_hours=round(statistics.median(leads), 6) if leads else None,
        minimum_lead_time_hours=round(min(leads), 6) if leads else None,
    )


@dataclass(frozen=True)
class RuleContribution:
    rule_code: str
    kind: str
    flips: int
    affected_records: tuple[str, ...]
    fixed_false_alarms: int
    new_misses: int
    caught_events: int
    new_false_alarms: int
    decision_changes: int
    benefit: int
    cost: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_code": self.rule_code,
            "kind": self.kind,
            "flips": self.flips,
            "affected_records": list(self.affected_records),
            "fixed_false_alarms": self.fixed_false_alarms,
            "new_misses": self.new_misses,
            "caught_events": self.caught_events,
            "new_false_alarms": self.new_false_alarms,
            "decision_changes": self.decision_changes,
            "benefit": self.benefit,
            "cost": self.cost,
        }


def _impact_of(
    baseline_alerted: bool, candidate_alerted: bool, actual_event: bool
) -> str:
    if baseline_alerted and not candidate_alerted:
        return "new_miss" if actual_event else "fixed_false_alarm"
    if not baseline_alerted and candidate_alerted:
        return "caught_event" if actual_event else "new_false_alarm"
    return "neutral"


def _rule_diffs(
    record: DomainRecord,
    baseline_context: Mapping[str, Any],
    package: RulePackage,
) -> list[tuple[str, str, bool, bool, float | None, float | None]]:
    """Return (code, kind, baseline_passed, candidate_passed, values) for rules
    whose pass/fail result differs between baseline and candidate context."""
    diffs: list[tuple[str, str, bool, bool, float | None, float | None]] = []
    baseline_results = {
        result.code: result for result in decide(record, baseline_context).rule_results
    }
    candidate_results = {
        result.code: result
        for result in decide(record, dict(baseline_context) | dict(package.context_overrides)).rule_results
    }
    for code, base_result in baseline_results.items():
        candidate_result = candidate_results[code]
        if base_result.passed != candidate_result.passed:
            diffs.append(
                (
                    code,
                    "rule",
                    base_result.passed,
                    candidate_result.passed,
                    base_result.score,
                    candidate_result.score,
                )
            )
    # Guard floor flips: guards read grouped metrics under named floors.
    guard_context = dict(baseline_context)
    guard_context["_metrics"] = grouped_metrics(record, guard_context)
    candidate_guard_context = dict(guard_context) | dict(package.context_overrides)
    for guard in GUARDS:
        base_ok, _ = guard(record, guard_context)
        candidate_ok, _ = guard(record, candidate_guard_context)
        if base_ok != candidate_ok:
            diffs.append((guard.__name__, "guard", base_ok, candidate_ok, None, None))
    return diffs


def evaluate_package(
    records: Sequence[DomainRecord],
    labels: Mapping[str, Label],
    package: RulePackage,
    base_context: Mapping[str, Any] | None = None,
) -> list[PackageOutcome]:
    base_context = dict(base_context or {})
    context = dict(base_context) | dict(package.context_overrides)
    outcomes: list[PackageOutcome] = []
    for record in records:
        label = labels[record.record_id]
        if not package.applies_to(station_of(record), label.event_type):
            continue
        decision = decide(record, context)
        alerted = decision.outcome in package.alert_outcomes
        lead = None
        if label.event_time is not None and _confusion(alerted, label.actual_event) == "tp":
            lead = (
                _parse_event_time(label.event_time) - _parse_event_time(record.occurred_at)
            ).total_seconds() / 3600.0
        outcomes.append(
            PackageOutcome(
                record_id=record.record_id,
                station_id=station_of(record),
                event_type=label.event_type,
                outcome=decision.outcome,
                alerted=alerted,
                score=decision.score,
                actual_event=label.actual_event,
                confusion=_confusion(alerted, label.actual_event),
                lead_time_hours=round(lead, 6) if lead is not None else None,
                event_time=label.event_time,
            )
        )
    return outcomes


@dataclass(frozen=True)
class GroupComparison:
    group_kind: str  # 'station' | 'event_type'
    group_value: str
    baseline: ConfusionMetrics
    candidate: ConfusionMetrics
    delta_false_positive: int
    delta_false_negative: int
    delta_alert_count: int
    delta_median_lead_time_hours: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "group_kind": self.group_kind,
            "group_value": self.group_value,
            "baseline": self.baseline.as_dict(),
            "candidate": self.candidate.as_dict(),
            "delta_false_positive": self.delta_false_positive,
            "delta_false_negative": self.delta_false_negative,
            "delta_alert_count": self.delta_alert_count,
            "delta_median_lead_time_hours": self.delta_median_lead_time_hours,
        }


def _group_comparisons(
    group_kind: str,
    baseline_outcomes: Sequence[PackageOutcome],
    candidate_outcomes: Sequence[PackageOutcome],
) -> list[GroupComparison]:
    attr = "station_id" if group_kind == "station" else "event_type"
    keys = sorted({getattr(item, attr) for item in (*baseline_outcomes, *candidate_outcomes)})
    comparisons: list[GroupComparison] = []
    for key in keys:
        base = [item for item in baseline_outcomes if getattr(item, attr) == key]
        cand = [item for item in candidate_outcomes if getattr(item, attr) == key]
        base_metrics = _metrics_from_outcomes(base)
        cand_metrics = _metrics_from_outcomes(cand)
        base_median = base_metrics.median_lead_time_hours
        cand_median = cand_metrics.median_lead_time_hours
        delta_median = (
            round(cand_median - base_median, 6)
            if base_median is not None and cand_median is not None
            else None
        )
        comparisons.append(
            GroupComparison(
                group_kind=group_kind,
                group_value=key,
                baseline=base_metrics,
                candidate=cand_metrics,
                delta_false_positive=cand_metrics.false_positive - base_metrics.false_positive,
                delta_false_negative=cand_metrics.false_negative - base_metrics.false_negative,
                delta_alert_count=cand_metrics.alert_count - base_metrics.alert_count,
                delta_median_lead_time_hours=delta_median,
            )
        )
    return comparisons


def _rule_contributions(flips: Sequence[RuleFlip]) -> list[RuleContribution]:
    grouped: dict[tuple[str, str], list[RuleFlip]] = {}
    for flip in flips:
        grouped.setdefault((flip.rule_code, flip.kind), []).append(flip)
    contributions: list[RuleContribution] = []
    for (code, kind), items in grouped.items():
        contributions.append(
            RuleContribution(
                rule_code=code,
                kind=kind,
                flips=len(items),
                affected_records=tuple(sorted({item.record_id for item in items})),
                fixed_false_alarms=sum(item.impact == "fixed_false_alarm" for item in items),
                new_misses=sum(item.impact == "new_miss" for item in items),
                caught_events=sum(item.impact == "caught_event" for item in items),
                new_false_alarms=sum(item.impact == "new_false_alarm" for item in items),
                decision_changes=sum(item.decision_changed for item in items),
                benefit=sum(item.impact in ("fixed_false_alarm", "caught_event") for item in items),
                cost=sum(item.impact in ("new_miss", "new_false_alarm") for item in items),
            )
        )
    return sorted(contributions, key=lambda item: (-item.benefit, item.cost, item.rule_code))


@dataclass(frozen=True)
class TrialPolicy:
    """Multi-criterion gate.  Minimum false alarms alone never qualifies."""

    max_new_misses: int = 0
    require_recall_non_regression: bool = True
    require_lead_time_non_regression: bool = True
    require_station_non_regression: bool = True
    require_event_type_non_regression: bool = True
    require_evidence_integrity: bool = True
    min_false_positive_reduction: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_new_misses": self.max_new_misses,
            "require_recall_non_regression": self.require_recall_non_regression,
            "require_lead_time_non_regression": self.require_lead_time_non_regression,
            "require_station_non_regression": self.require_station_non_regression,
            "require_event_type_non_regression": self.require_event_type_non_regression,
            "require_evidence_integrity": self.require_evidence_integrity,
            "min_false_positive_reduction": self.min_false_positive_reduction,
        }


@dataclass(frozen=True)
class EligibilityVerdict:
    eligible: bool
    blocking_reasons: tuple[str, ...]
    passed_checks: tuple[str, ...]
    policy: TrialPolicy
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "blocking_reasons": list(self.blocking_reasons),
            "passed_checks": list(self.passed_checks),
            "policy": self.policy.as_dict(),
            "note": self.note,
        }


def evaluate_eligibility(
    baseline_metrics: ConfusionMetrics,
    candidate_metrics: ConfusionMetrics,
    station_groups: Sequence[GroupComparison],
    event_type_groups: Sequence[GroupComparison],
    policy: TrialPolicy | None = None,
) -> EligibilityVerdict:
    policy = policy or TrialPolicy()
    blocking: list[str] = []
    passed: list[str] = []

    new_misses = candidate_metrics.false_negative - baseline_metrics.false_negative
    if new_misses > policy.max_new_misses:
        blocking.append(f"candidate introduces {new_misses} new miss(es)")
    else:
        passed.append("no new misses beyond policy allowance")

    if policy.require_recall_non_regression:
        base_recall = baseline_metrics.recall
        cand_recall = candidate_metrics.recall
        if base_recall is not None and (cand_recall is None or cand_recall + 1e-9 < base_recall):
            blocking.append(f"recall regresses {base_recall} -> {cand_recall}")
        else:
            passed.append("recall does not regress")

    if policy.require_lead_time_non_regression:
        base_lead = baseline_metrics.median_lead_time_hours
        cand_lead = candidate_metrics.median_lead_time_hours
        if base_lead is not None and (cand_lead is None or cand_lead + 1e-9 < base_lead):
            blocking.append(f"median lead time regresses {base_lead}h -> {cand_lead}h")
        else:
            passed.append("median lead time does not regress")

    if policy.require_station_non_regression and any(
        group.delta_false_negative > 0 for group in station_groups
    ):
        blocking.append("at least one station gains misses")
    elif policy.require_station_non_regression:
        passed.append("no station gains misses")

    if policy.require_event_type_non_regression and any(
        group.delta_false_negative > 0 for group in event_type_groups
    ):
        blocking.append("at least one event type gains misses")
    elif policy.require_event_type_non_regression:
        passed.append("no event type gains misses")

    reduction = baseline_metrics.false_positive - candidate_metrics.false_positive
    if reduction < policy.min_false_positive_reduction:
        blocking.append("candidate does not reduce false alarms beyond policy minimum")
    else:
        passed.append(f"false alarms reduced by {reduction}")

    if policy.require_evidence_integrity:
        passed.append("replay evidence fingerprint included for review")

    return EligibilityVerdict(
        eligible=not blocking,
        blocking_reasons=tuple(blocking),
        passed_checks=tuple(passed),
        policy=policy,
        note=(
            "eligibility requires every check to pass; the minimum-false-alarm "
            "package is rejected when recall or lead time regresses"
        ),
    )


@dataclass(frozen=True)
class ReplayReport:
    replay_id: str
    baseline_package: dict[str, Any]
    candidate_package: dict[str, Any]
    observation_fingerprints: dict[str, str]
    label_hash: str
    baseline_outcomes: list[PackageOutcome]
    candidate_outcomes: list[PackageOutcome]
    baseline_metrics: ConfusionMetrics
    candidate_metrics: ConfusionMetrics
    station_comparisons: list[GroupComparison]
    event_type_comparisons: list[GroupComparison]
    rule_contributions: list[RuleContribution]
    rule_flips: list[RuleFlip]
    eligibility: EligibilityVerdict
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "baseline_package": self.baseline_package,
            "candidate_package": self.candidate_package,
            "observation_fingerprints": self.observation_fingerprints,
            "label_hash": self.label_hash,
            "baseline_outcomes": [item.as_dict() for item in self.baseline_outcomes],
            "candidate_outcomes": [item.as_dict() for item in self.candidate_outcomes],
            "baseline_metrics": self.baseline_metrics.as_dict(),
            "candidate_metrics": self.candidate_metrics.as_dict(),
            "station_comparisons": [item.as_dict() for item in self.station_comparisons],
            "event_type_comparisons": [item.as_dict() for item in self.event_type_comparisons],
            "rule_contributions": [item.as_dict() for item in self.rule_contributions],
            "rule_flips": [item.as_dict() for item in self.rule_flips],
            "eligibility": self.eligibility.as_dict(),
            "fingerprint": self.fingerprint,
        }


def replay_candidate(
    records: Sequence[DomainRecord],
    raw_labels: Mapping[str, Any],
    candidate: RulePackage,
    base_context: Mapping[str, Any] | None = None,
    policy: TrialPolicy | None = None,
    baseline: RulePackage | None = None,
) -> ReplayReport:
    """Replay historical observations under baseline and one candidate package."""
    baseline = baseline or baseline_package()
    if baseline.package_id == candidate.package_id and baseline.version == candidate.version:
        raise ContractError("candidate package must differ from the baseline")
    labels = normalize_labels(records, raw_labels)
    base_context = dict(base_context or {})

    # Fair comparison: a scoped candidate is compared with the baseline on the
    # exact same in-scope observations, never against the whole fleet.
    scoped_records = [
        record
        for record in records
        if candidate.applies_to(station_of(record), labels[record.record_id].event_type)
    ]
    if not scoped_records:
        raise ContractError("candidate scope matches no labelled observations")

    baseline_outcomes = evaluate_package(scoped_records, labels, baseline, base_context)
    candidate_outcomes = evaluate_package(scoped_records, labels, candidate, base_context)
    baseline_by_id = {item.record_id: item for item in baseline_outcomes}

    flips: list[RuleFlip] = []
    for candidate_outcome in candidate_outcomes:
        record = next(item for item in records if item.record_id == candidate_outcome.record_id)
        label = labels[record.record_id]
        baseline_outcome = baseline_by_id[record.record_id]
        decision_changed = baseline_outcome.outcome != candidate_outcome.outcome
        if not decision_changed:
            continue
        for code, kind, base_ok, cand_ok, base_value, cand_value in _rule_diffs(
            record, base_context, candidate
        ):
            flips.append(
                RuleFlip(
                    record_id=record.record_id,
                    station_id=candidate_outcome.station_id,
                    event_type=label.event_type,
                    rule_code=code,
                    kind=kind,
                    baseline_passed=base_ok,
                    candidate_passed=cand_ok,
                    baseline_value=base_value,
                    candidate_value=cand_value,
                    decision_changed=True,
                    label_actual_event=label.actual_event,
                    impact=_impact_of(
                        baseline_outcome.alerted,
                        candidate_outcome.alerted,
                        label.actual_event,
                    ),
                )
            )

    baseline_metrics = _metrics_from_outcomes(baseline_outcomes)
    candidate_metrics = _metrics_from_outcomes(candidate_outcomes)
    station_groups = _group_comparisons("station", baseline_outcomes, candidate_outcomes)
    event_type_groups = _group_comparisons("event_type", baseline_outcomes, candidate_outcomes)
    contributions = _rule_contributions(flips)
    eligibility = evaluate_eligibility(
        baseline_metrics, candidate_metrics, station_groups, event_type_groups, policy
    )

    observation_fingerprints = {
        record.record_id: record.fingerprint
        for record in records
        if record.record_id in {item.record_id for item in candidate_outcomes}
    }
    label_hash = stable_hash(sorted((key, value.actual_event, value.event_type, value.event_time)
                                    for key, value in labels.items()))
    replay_id = stable_hash(
        {
            "candidate": candidate.fingerprint,
            "baseline": baseline.fingerprint,
            "observations": observation_fingerprints,
            "label_hash": label_hash,
            "context": dict(sorted((base_context or {}).items())),
        }
    )[:24]
    report = ReplayReport(
        replay_id=replay_id,
        baseline_package=baseline.as_dict(),
        candidate_package=candidate.as_dict(),
        observation_fingerprints=observation_fingerprints,
        label_hash=label_hash,
        baseline_outcomes=baseline_outcomes,
        candidate_outcomes=candidate_outcomes,
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        station_comparisons=station_groups,
        event_type_comparisons=event_type_groups,
        rule_contributions=contributions,
        rule_flips=flips,
        eligibility=eligibility,
        fingerprint="",
    )
    # Fingerprint covers the complete serialised report, excluding itself.
    full_body = report.as_dict()
    full_body.pop("fingerprint")
    return dataclasses.replace(report, fingerprint=stable_hash(full_body))


def replay_portfolio(
    records: Sequence[DomainRecord],
    raw_labels: Mapping[str, Any],
    candidates: Sequence[RulePackage],
    base_context: Mapping[str, Any] | None = None,
    policy: TrialPolicy | None = None,
) -> list[ReplayReport]:
    """Replay every candidate against the same frozen evidence, deterministically."""
    return [
        replay_candidate(records, raw_labels, candidate, base_context, policy)
        for candidate in candidates
    ]


def select_evidence_backed(reports: Sequence[ReplayReport]) -> ReplayReport | None:
    """Choose among eligible candidates only; never a minimum-false-alarm-only one.

    Among packages that pass every eligibility check we prefer the largest false
    positive reduction, then the best recall, then the smallest fingerprint for a
    deterministic tie-break.  Ineligible packages (including any that only win on
    false alarms) are never selected.
    """
    eligible = [report for report in reports if report.eligibility.eligible]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda report: (
            -(report.baseline_metrics.false_positive - report.candidate_metrics.false_positive),
            -(report.candidate_metrics.recall or -1.0),
            report.fingerprint,
        ),
    )[0]


def canonical_report(report: ReplayReport) -> str:
    return canonical_json(report.as_dict())
