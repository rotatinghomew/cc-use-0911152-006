from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Iterable

from basin_warning.observations.hydro_event import DomainRecord, bounded, finite_number


@dataclass(frozen=True)
class StationSignal:
    station_id: str
    risk: float
    freshness: float
    quality: float
    lead_time: float


def station_signal(record: DomainRecord) -> StationSignal:
    rainfall = bounded(finite_number(record.payload.get("rainfall_mm", 0.0)) / 250.0)
    water = bounded(finite_number(record.payload.get("water_level_m", 0.0)) / 15.0)
    flow = bounded(finite_number(record.payload.get("flow_rate", 0.0)) / 2500.0)
    opening = bounded(finite_number(record.payload.get("gate_opening", 0.0)))
    age = max(0.0, finite_number(record.payload.get("sensor_age_min", 0.0)))
    quality_flag = bounded(finite_number(record.payload.get("quality_flag", 0.0)))
    freshness = bounded(1.0 - age / 180.0)
    risk = bounded(rainfall * 0.30 + water * 0.35 + flow * 0.25 + (1.0 - opening) * 0.10)
    lead = max(0.0, finite_number(record.payload.get("forecast_horizon_h", 0.0)) - finite_number(record.payload.get("upstream_delay", 0.0)))
    return StationSignal(str(record.payload.get("station_id", record.record_id)), risk, freshness, quality_flag, lead)


def event_watermark(records: Iterable[DomainRecord]) -> dict[str, float]:
    signals = [station_signal(row) for row in records]
    if not signals:
        return {"risk": 0.0, "freshness": 0.0, "agreement": 0.0, "lead_time": 0.0}
    risks = [item.risk for item in signals]
    agreement = bounded(1.0 - (statistics.pstdev(risks) if len(risks) > 1 else 0.0))
    weighted = sum(item.risk * item.freshness * item.quality for item in signals)
    weights = sum(item.freshness * item.quality for item in signals)
    return {"risk": weighted / weights if weights else max(risks),
            "freshness": statistics.fmean(item.freshness for item in signals), "agreement": agreement,
            "lead_time": min(item.lead_time for item in signals)}


def alert_level(watermark: dict[str, float], previous: str = "observing") -> str:
    risk = watermark["risk"] * (0.7 + watermark["agreement"] * 0.3)
    thresholds = [(0.80, "critical"), (0.60, "warning"), (0.40, "watch")]
    target = next((name for threshold, name in thresholds if risk >= threshold), "observing")
    order = ["observing", "watch", "warning", "critical"]
    if previous in order and order.index(target) < order.index(previous) and watermark["freshness"] < 0.75:
        return previous
    return target


def delivery_risk(record: DomainRecord) -> float:
    exposure = bounded(finite_number(record.payload.get("population_exposure", 0.0)) / 100000.0)
    channels = max(1.0, finite_number(record.payload.get("delivery_channels", 1.0)))
    acknowledgements = bounded(finite_number(record.payload.get("ack_rate", 0.0)))
    return bounded(exposure * 0.5 + (1.0 - acknowledgements) * 0.4 + 0.1 / channels)


def derive_context(record: DomainRecord, repository: Any) -> dict[str, float]:
    rows = repository.list_records() or [record]
    watermark = event_watermark(rows)
    level = alert_level(watermark)
    rank = {"observing": 0.2, "watch": 0.4, "warning": 0.7, "critical": 1.0}[level]
    delivery = delivery_risk(record)
    return {"fusion_confidence_weight": 0.6 + watermark["agreement"] * 0.5,
            "lead_time_weight": 0.6 + bounded(watermark["lead_time"] / 72.0) * 0.5,
            "miss_risk_weight": 0.7 + rank * 0.6, "delivery_reach_weight": 1.1 - delivery * 0.4,
            "station_disagreement_weight": 1.2 - watermark["agreement"] * 0.4}
