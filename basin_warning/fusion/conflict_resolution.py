from __future__ import annotations

import math
from typing import Any, Callable, Mapping

from basin_warning.observations.hydro_event import DomainRecord, RuleResult, bounded, finite_number, normalized_text

RuleFunction = Callable[[DomainRecord, Mapping[str, Any]], RuleResult]

def _number(record: DomainRecord, field: str) -> float:
    value = record.payload.get(field)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return finite_number(value)
    text = normalized_text(value)
    if not text:
        return 0.0
    try:
        return finite_number(text)
    except ValueError:
        return float(sum(ord(ch) for ch in text) % 101)

def _context_number(context: Mapping[str, Any], key: str, default: float) -> float:
    try:
        return finite_number(context.get(key, default))
    except ValueError:
        return default

def _result(code: str, value: float, threshold: float, higher_is_better: bool, message: str, evidence: dict[str, Any]) -> RuleResult:
    distance = (value - threshold) if higher_is_better else (threshold - value)
    passed = distance >= 0
    scale = max(1.0, abs(threshold))
    score = bounded(0.5 + distance / (2.0 * scale))
    severity = 'info' if passed else ('critical' if score < 0.2 else 'error')
    return RuleResult(code, passed, score, severity, message, evidence)

def check_station_id_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_station_id_presence_threshold', 10.333)
    return _result('check_station_id_presence', adjusted, threshold, True, 'validates station_id presence',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_station_id_range_threshold', 12.667)
    return _result('check_station_id_range', adjusted, threshold, True, 'validates station_id range',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_station_id_stability_threshold', 15.0)
    return _result('check_station_id_stability', adjusted, threshold, False, 'validates station_id stability',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_station_id_freshness_threshold', 17.333)
    return _result('check_station_id_freshness', adjusted, threshold, True, 'validates station_id freshness',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_station_id_coverage_threshold', 19.667)
    return _result('check_station_id_coverage', adjusted, threshold, True, 'validates station_id coverage',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_station_id_consistency_threshold', 22.0)
    return _result('check_station_id_consistency', adjusted, threshold, False, 'validates station_id consistency',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_station_id_risk_threshold', 24.333)
    return _result('check_station_id_risk', adjusted, threshold, True, 'validates station_id risk',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_station_id_confidence_threshold', 26.667)
    return _result('check_station_id_confidence', adjusted, threshold, True, 'validates station_id confidence',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_station_id_dependency_threshold', 29.0)
    return _result('check_station_id_dependency', adjusted, threshold, False, 'validates station_id dependency',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_station_id_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'station_id')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_station_id_readiness_threshold', 31.333)
    return _result('check_station_id_readiness', adjusted, threshold, True, 'validates station_id readiness',
                   {'field': 'station_id', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_rainfall_mm_presence_threshold', 9.333)
    return _result('check_rainfall_mm_presence', adjusted, threshold, True, 'validates rainfall_mm presence',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_rainfall_mm_range_threshold', 11.667)
    return _result('check_rainfall_mm_range', adjusted, threshold, False, 'validates rainfall_mm range',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_rainfall_mm_stability_threshold', 14.0)
    return _result('check_rainfall_mm_stability', adjusted, threshold, True, 'validates rainfall_mm stability',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_rainfall_mm_freshness_threshold', 16.333)
    return _result('check_rainfall_mm_freshness', adjusted, threshold, True, 'validates rainfall_mm freshness',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_rainfall_mm_coverage_threshold', 18.667)
    return _result('check_rainfall_mm_coverage', adjusted, threshold, False, 'validates rainfall_mm coverage',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_rainfall_mm_consistency_threshold', 21.0)
    return _result('check_rainfall_mm_consistency', adjusted, threshold, True, 'validates rainfall_mm consistency',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_rainfall_mm_risk_threshold', 23.333)
    return _result('check_rainfall_mm_risk', adjusted, threshold, True, 'validates rainfall_mm risk',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_rainfall_mm_confidence_threshold', 25.667)
    return _result('check_rainfall_mm_confidence', adjusted, threshold, False, 'validates rainfall_mm confidence',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_rainfall_mm_dependency_threshold', 28.0)
    return _result('check_rainfall_mm_dependency', adjusted, threshold, True, 'validates rainfall_mm dependency',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_rainfall_mm_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'rainfall_mm')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_rainfall_mm_readiness_threshold', 30.333)
    return _result('check_rainfall_mm_readiness', adjusted, threshold, True, 'validates rainfall_mm readiness',
                   {'field': 'rainfall_mm', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_water_level_m_presence_threshold', 8.333)
    return _result('check_water_level_m_presence', adjusted, threshold, False, 'validates water_level_m presence',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_water_level_m_range_threshold', 10.667)
    return _result('check_water_level_m_range', adjusted, threshold, True, 'validates water_level_m range',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_water_level_m_stability_threshold', 13.0)
    return _result('check_water_level_m_stability', adjusted, threshold, True, 'validates water_level_m stability',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_water_level_m_freshness_threshold', 15.333)
    return _result('check_water_level_m_freshness', adjusted, threshold, False, 'validates water_level_m freshness',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_water_level_m_coverage_threshold', 17.667)
    return _result('check_water_level_m_coverage', adjusted, threshold, True, 'validates water_level_m coverage',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_water_level_m_consistency_threshold', 20.0)
    return _result('check_water_level_m_consistency', adjusted, threshold, True, 'validates water_level_m consistency',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_water_level_m_risk_threshold', 22.333)
    return _result('check_water_level_m_risk', adjusted, threshold, False, 'validates water_level_m risk',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_water_level_m_confidence_threshold', 24.667)
    return _result('check_water_level_m_confidence', adjusted, threshold, True, 'validates water_level_m confidence',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_water_level_m_dependency_threshold', 27.0)
    return _result('check_water_level_m_dependency', adjusted, threshold, True, 'validates water_level_m dependency',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_water_level_m_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'water_level_m')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_water_level_m_readiness_threshold', 29.333)
    return _result('check_water_level_m_readiness', adjusted, threshold, False, 'validates water_level_m readiness',
                   {'field': 'water_level_m', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_flow_rate_presence_threshold', 31.667)
    return _result('check_flow_rate_presence', adjusted, threshold, True, 'validates flow_rate presence',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_flow_rate_range_threshold', 9.667)
    return _result('check_flow_rate_range', adjusted, threshold, True, 'validates flow_rate range',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_flow_rate_stability_threshold', 12.0)
    return _result('check_flow_rate_stability', adjusted, threshold, False, 'validates flow_rate stability',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_flow_rate_freshness_threshold', 14.333)
    return _result('check_flow_rate_freshness', adjusted, threshold, True, 'validates flow_rate freshness',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_flow_rate_coverage_threshold', 16.667)
    return _result('check_flow_rate_coverage', adjusted, threshold, True, 'validates flow_rate coverage',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_flow_rate_consistency_threshold', 19.0)
    return _result('check_flow_rate_consistency', adjusted, threshold, False, 'validates flow_rate consistency',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_flow_rate_risk_threshold', 21.333)
    return _result('check_flow_rate_risk', adjusted, threshold, True, 'validates flow_rate risk',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_flow_rate_confidence_threshold', 23.667)
    return _result('check_flow_rate_confidence', adjusted, threshold, True, 'validates flow_rate confidence',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_flow_rate_dependency_threshold', 26.0)
    return _result('check_flow_rate_dependency', adjusted, threshold, False, 'validates flow_rate dependency',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_flow_rate_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'flow_rate')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_flow_rate_readiness_threshold', 28.333)
    return _result('check_flow_rate_readiness', adjusted, threshold, True, 'validates flow_rate readiness',
                   {'field': 'flow_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_gate_opening_presence_threshold', 30.667)
    return _result('check_gate_opening_presence', adjusted, threshold, True, 'validates gate_opening presence',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_gate_opening_range_threshold', 8.667)
    return _result('check_gate_opening_range', adjusted, threshold, False, 'validates gate_opening range',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_gate_opening_stability_threshold', 11.0)
    return _result('check_gate_opening_stability', adjusted, threshold, True, 'validates gate_opening stability',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_gate_opening_freshness_threshold', 13.333)
    return _result('check_gate_opening_freshness', adjusted, threshold, True, 'validates gate_opening freshness',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_gate_opening_coverage_threshold', 15.667)
    return _result('check_gate_opening_coverage', adjusted, threshold, False, 'validates gate_opening coverage',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_gate_opening_consistency_threshold', 18.0)
    return _result('check_gate_opening_consistency', adjusted, threshold, True, 'validates gate_opening consistency',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_gate_opening_risk_threshold', 20.333)
    return _result('check_gate_opening_risk', adjusted, threshold, True, 'validates gate_opening risk',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_gate_opening_confidence_threshold', 22.667)
    return _result('check_gate_opening_confidence', adjusted, threshold, False, 'validates gate_opening confidence',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_gate_opening_dependency_threshold', 25.0)
    return _result('check_gate_opening_dependency', adjusted, threshold, True, 'validates gate_opening dependency',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_gate_opening_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'gate_opening')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_gate_opening_readiness_threshold', 27.333)
    return _result('check_gate_opening_readiness', adjusted, threshold, True, 'validates gate_opening readiness',
                   {'field': 'gate_opening', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_forecast_horizon_h_presence_threshold', 29.667)
    return _result('check_forecast_horizon_h_presence', adjusted, threshold, False, 'validates forecast_horizon_h presence',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_forecast_horizon_h_range_threshold', 32.0)
    return _result('check_forecast_horizon_h_range', adjusted, threshold, True, 'validates forecast_horizon_h range',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_forecast_horizon_h_stability_threshold', 10.0)
    return _result('check_forecast_horizon_h_stability', adjusted, threshold, True, 'validates forecast_horizon_h stability',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_forecast_horizon_h_freshness_threshold', 12.333)
    return _result('check_forecast_horizon_h_freshness', adjusted, threshold, False, 'validates forecast_horizon_h freshness',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_forecast_horizon_h_coverage_threshold', 14.667)
    return _result('check_forecast_horizon_h_coverage', adjusted, threshold, True, 'validates forecast_horizon_h coverage',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_forecast_horizon_h_consistency_threshold', 17.0)
    return _result('check_forecast_horizon_h_consistency', adjusted, threshold, True, 'validates forecast_horizon_h consistency',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_forecast_horizon_h_risk_threshold', 19.333)
    return _result('check_forecast_horizon_h_risk', adjusted, threshold, False, 'validates forecast_horizon_h risk',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_forecast_horizon_h_confidence_threshold', 21.667)
    return _result('check_forecast_horizon_h_confidence', adjusted, threshold, True, 'validates forecast_horizon_h confidence',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_forecast_horizon_h_dependency_threshold', 24.0)
    return _result('check_forecast_horizon_h_dependency', adjusted, threshold, True, 'validates forecast_horizon_h dependency',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_forecast_horizon_h_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'forecast_horizon_h')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_forecast_horizon_h_readiness_threshold', 26.333)
    return _result('check_forecast_horizon_h_readiness', adjusted, threshold, False, 'validates forecast_horizon_h readiness',
                   {'field': 'forecast_horizon_h', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_sensor_age_min_presence_threshold', 28.667)
    return _result('check_sensor_age_min_presence', adjusted, threshold, True, 'validates sensor_age_min presence',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_sensor_age_min_range_threshold', 31.0)
    return _result('check_sensor_age_min_range', adjusted, threshold, True, 'validates sensor_age_min range',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_sensor_age_min_stability_threshold', 9.0)
    return _result('check_sensor_age_min_stability', adjusted, threshold, False, 'validates sensor_age_min stability',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_sensor_age_min_freshness_threshold', 11.333)
    return _result('check_sensor_age_min_freshness', adjusted, threshold, True, 'validates sensor_age_min freshness',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_sensor_age_min_coverage_threshold', 13.667)
    return _result('check_sensor_age_min_coverage', adjusted, threshold, True, 'validates sensor_age_min coverage',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_sensor_age_min_consistency_threshold', 16.0)
    return _result('check_sensor_age_min_consistency', adjusted, threshold, False, 'validates sensor_age_min consistency',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_sensor_age_min_risk_threshold', 18.333)
    return _result('check_sensor_age_min_risk', adjusted, threshold, True, 'validates sensor_age_min risk',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_sensor_age_min_confidence_threshold', 20.667)
    return _result('check_sensor_age_min_confidence', adjusted, threshold, True, 'validates sensor_age_min confidence',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_sensor_age_min_dependency_threshold', 23.0)
    return _result('check_sensor_age_min_dependency', adjusted, threshold, False, 'validates sensor_age_min dependency',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_sensor_age_min_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'sensor_age_min')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_sensor_age_min_readiness_threshold', 25.333)
    return _result('check_sensor_age_min_readiness', adjusted, threshold, True, 'validates sensor_age_min readiness',
                   {'field': 'sensor_age_min', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_quality_flag_presence_threshold', 27.667)
    return _result('check_quality_flag_presence', adjusted, threshold, True, 'validates quality_flag presence',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_quality_flag_range_threshold', 30.0)
    return _result('check_quality_flag_range', adjusted, threshold, False, 'validates quality_flag range',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_quality_flag_stability_threshold', 8.0)
    return _result('check_quality_flag_stability', adjusted, threshold, True, 'validates quality_flag stability',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_quality_flag_freshness_threshold', 10.333)
    return _result('check_quality_flag_freshness', adjusted, threshold, True, 'validates quality_flag freshness',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_quality_flag_coverage_threshold', 12.667)
    return _result('check_quality_flag_coverage', adjusted, threshold, False, 'validates quality_flag coverage',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_quality_flag_consistency_threshold', 15.0)
    return _result('check_quality_flag_consistency', adjusted, threshold, True, 'validates quality_flag consistency',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_quality_flag_risk_threshold', 17.333)
    return _result('check_quality_flag_risk', adjusted, threshold, True, 'validates quality_flag risk',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_quality_flag_confidence_threshold', 19.667)
    return _result('check_quality_flag_confidence', adjusted, threshold, False, 'validates quality_flag confidence',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_quality_flag_dependency_threshold', 22.0)
    return _result('check_quality_flag_dependency', adjusted, threshold, True, 'validates quality_flag dependency',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_quality_flag_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'quality_flag')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_quality_flag_readiness_threshold', 24.333)
    return _result('check_quality_flag_readiness', adjusted, threshold, True, 'validates quality_flag readiness',
                   {'field': 'quality_flag', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_upstream_delay_presence_threshold', 26.667)
    return _result('check_upstream_delay_presence', adjusted, threshold, False, 'validates upstream_delay presence',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_upstream_delay_range_threshold', 29.0)
    return _result('check_upstream_delay_range', adjusted, threshold, True, 'validates upstream_delay range',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_upstream_delay_stability_threshold', 31.333)
    return _result('check_upstream_delay_stability', adjusted, threshold, True, 'validates upstream_delay stability',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_upstream_delay_freshness_threshold', 9.333)
    return _result('check_upstream_delay_freshness', adjusted, threshold, False, 'validates upstream_delay freshness',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_upstream_delay_coverage_threshold', 11.667)
    return _result('check_upstream_delay_coverage', adjusted, threshold, True, 'validates upstream_delay coverage',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_upstream_delay_consistency_threshold', 14.0)
    return _result('check_upstream_delay_consistency', adjusted, threshold, True, 'validates upstream_delay consistency',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_upstream_delay_risk_threshold', 16.333)
    return _result('check_upstream_delay_risk', adjusted, threshold, False, 'validates upstream_delay risk',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_upstream_delay_confidence_threshold', 18.667)
    return _result('check_upstream_delay_confidence', adjusted, threshold, True, 'validates upstream_delay confidence',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_upstream_delay_dependency_threshold', 21.0)
    return _result('check_upstream_delay_dependency', adjusted, threshold, True, 'validates upstream_delay dependency',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_upstream_delay_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'upstream_delay')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_upstream_delay_readiness_threshold', 23.333)
    return _result('check_upstream_delay_readiness', adjusted, threshold, False, 'validates upstream_delay readiness',
                   {'field': 'upstream_delay', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_population_exposure_presence_threshold', 25.667)
    return _result('check_population_exposure_presence', adjusted, threshold, True, 'validates population_exposure presence',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_population_exposure_range_threshold', 28.0)
    return _result('check_population_exposure_range', adjusted, threshold, True, 'validates population_exposure range',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_population_exposure_stability_threshold', 30.333)
    return _result('check_population_exposure_stability', adjusted, threshold, False, 'validates population_exposure stability',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_population_exposure_freshness_threshold', 8.333)
    return _result('check_population_exposure_freshness', adjusted, threshold, True, 'validates population_exposure freshness',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_population_exposure_coverage_threshold', 10.667)
    return _result('check_population_exposure_coverage', adjusted, threshold, True, 'validates population_exposure coverage',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_population_exposure_consistency_threshold', 13.0)
    return _result('check_population_exposure_consistency', adjusted, threshold, False, 'validates population_exposure consistency',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_population_exposure_risk_threshold', 15.333)
    return _result('check_population_exposure_risk', adjusted, threshold, True, 'validates population_exposure risk',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_population_exposure_confidence_threshold', 17.667)
    return _result('check_population_exposure_confidence', adjusted, threshold, True, 'validates population_exposure confidence',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_population_exposure_dependency_threshold', 20.0)
    return _result('check_population_exposure_dependency', adjusted, threshold, False, 'validates population_exposure dependency',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_population_exposure_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'population_exposure')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_population_exposure_readiness_threshold', 22.333)
    return _result('check_population_exposure_readiness', adjusted, threshold, True, 'validates population_exposure readiness',
                   {'field': 'population_exposure', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_delivery_channels_presence_threshold', 24.667)
    return _result('check_delivery_channels_presence', adjusted, threshold, True, 'validates delivery_channels presence',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_delivery_channels_range_threshold', 27.0)
    return _result('check_delivery_channels_range', adjusted, threshold, False, 'validates delivery_channels range',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_delivery_channels_stability_threshold', 29.333)
    return _result('check_delivery_channels_stability', adjusted, threshold, True, 'validates delivery_channels stability',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_delivery_channels_freshness_threshold', 31.667)
    return _result('check_delivery_channels_freshness', adjusted, threshold, True, 'validates delivery_channels freshness',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_delivery_channels_coverage_threshold', 9.667)
    return _result('check_delivery_channels_coverage', adjusted, threshold, False, 'validates delivery_channels coverage',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_delivery_channels_consistency_threshold', 12.0)
    return _result('check_delivery_channels_consistency', adjusted, threshold, True, 'validates delivery_channels consistency',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_delivery_channels_risk_threshold', 14.333)
    return _result('check_delivery_channels_risk', adjusted, threshold, True, 'validates delivery_channels risk',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_delivery_channels_confidence_threshold', 16.667)
    return _result('check_delivery_channels_confidence', adjusted, threshold, False, 'validates delivery_channels confidence',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_delivery_channels_dependency_threshold', 19.0)
    return _result('check_delivery_channels_dependency', adjusted, threshold, True, 'validates delivery_channels dependency',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_delivery_channels_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'delivery_channels')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 0.0
    threshold = _context_number(context, 'check_delivery_channels_readiness_threshold', 21.333)
    return _result('check_delivery_channels_readiness', adjusted, threshold, True, 'validates delivery_channels readiness',
                   {'field': 'delivery_channels', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_presence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'presence_weight', 1.1)
    adjusted = raw * weight + 0.17
    threshold = _context_number(context, 'check_ack_rate_presence_threshold', 23.667)
    return _result('check_ack_rate_presence', adjusted, threshold, False, 'validates ack_rate presence',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_range(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'range_weight', 1.2)
    adjusted = raw * weight + 0.34
    threshold = _context_number(context, 'check_ack_rate_range_threshold', 26.0)
    return _result('check_ack_rate_range', adjusted, threshold, True, 'validates ack_rate range',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_stability(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'stability_weight', 1.3)
    adjusted = raw * weight + 0.51
    threshold = _context_number(context, 'check_ack_rate_stability_threshold', 28.333)
    return _result('check_ack_rate_stability', adjusted, threshold, True, 'validates ack_rate stability',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_freshness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'freshness_weight', 1.4)
    adjusted = raw * weight + 0.68
    threshold = _context_number(context, 'check_ack_rate_freshness_threshold', 30.667)
    return _result('check_ack_rate_freshness', adjusted, threshold, False, 'validates ack_rate freshness',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_coverage(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'coverage_weight', 1.0)
    adjusted = raw * weight + 0.8500000000000001
    threshold = _context_number(context, 'check_ack_rate_coverage_threshold', 8.667)
    return _result('check_ack_rate_coverage', adjusted, threshold, True, 'validates ack_rate coverage',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_consistency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'consistency_weight', 1.1)
    adjusted = raw * weight + 1.02
    threshold = _context_number(context, 'check_ack_rate_consistency_threshold', 11.0)
    return _result('check_ack_rate_consistency', adjusted, threshold, True, 'validates ack_rate consistency',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_risk(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'risk_weight', 1.2)
    adjusted = raw * weight + 1.1900000000000002
    threshold = _context_number(context, 'check_ack_rate_risk_threshold', 13.333)
    return _result('check_ack_rate_risk', adjusted, threshold, False, 'validates ack_rate risk',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_confidence(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'confidence_weight', 1.3)
    adjusted = raw * weight + 1.36
    threshold = _context_number(context, 'check_ack_rate_confidence_threshold', 15.667)
    return _result('check_ack_rate_confidence', adjusted, threshold, True, 'validates ack_rate confidence',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_dependency(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'dependency_weight', 1.4)
    adjusted = raw * weight + 1.53
    threshold = _context_number(context, 'check_ack_rate_dependency_threshold', 18.0)
    return _result('check_ack_rate_dependency', adjusted, threshold, True, 'validates ack_rate dependency',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

def check_ack_rate_readiness(record: DomainRecord, context: Mapping[str, Any]) -> RuleResult:
    raw = _number(record, 'ack_rate')
    weight = _context_number(context, 'readiness_weight', 1.0)
    adjusted = raw * weight + 1.7000000000000002
    threshold = _context_number(context, 'check_ack_rate_readiness_threshold', 20.333)
    return _result('check_ack_rate_readiness', adjusted, threshold, False, 'validates ack_rate readiness',
                   {'field': 'ack_rate', 'raw': raw, 'weight': weight, 'adjusted': adjusted, 'threshold': threshold})

RULES: tuple[RuleFunction, ...] = (
    check_station_id_presence,
    check_station_id_range,
    check_station_id_stability,
    check_station_id_freshness,
    check_station_id_coverage,
    check_station_id_consistency,
    check_station_id_risk,
    check_station_id_confidence,
    check_station_id_dependency,
    check_station_id_readiness,
    check_rainfall_mm_presence,
    check_rainfall_mm_range,
    check_rainfall_mm_stability,
    check_rainfall_mm_freshness,
    check_rainfall_mm_coverage,
    check_rainfall_mm_consistency,
    check_rainfall_mm_risk,
    check_rainfall_mm_confidence,
    check_rainfall_mm_dependency,
    check_rainfall_mm_readiness,
    check_water_level_m_presence,
    check_water_level_m_range,
    check_water_level_m_stability,
    check_water_level_m_freshness,
    check_water_level_m_coverage,
    check_water_level_m_consistency,
    check_water_level_m_risk,
    check_water_level_m_confidence,
    check_water_level_m_dependency,
    check_water_level_m_readiness,
    check_flow_rate_presence,
    check_flow_rate_range,
    check_flow_rate_stability,
    check_flow_rate_freshness,
    check_flow_rate_coverage,
    check_flow_rate_consistency,
    check_flow_rate_risk,
    check_flow_rate_confidence,
    check_flow_rate_dependency,
    check_flow_rate_readiness,
    check_gate_opening_presence,
    check_gate_opening_range,
    check_gate_opening_stability,
    check_gate_opening_freshness,
    check_gate_opening_coverage,
    check_gate_opening_consistency,
    check_gate_opening_risk,
    check_gate_opening_confidence,
    check_gate_opening_dependency,
    check_gate_opening_readiness,
    check_forecast_horizon_h_presence,
    check_forecast_horizon_h_range,
    check_forecast_horizon_h_stability,
    check_forecast_horizon_h_freshness,
    check_forecast_horizon_h_coverage,
    check_forecast_horizon_h_consistency,
    check_forecast_horizon_h_risk,
    check_forecast_horizon_h_confidence,
    check_forecast_horizon_h_dependency,
    check_forecast_horizon_h_readiness,
    check_sensor_age_min_presence,
    check_sensor_age_min_range,
    check_sensor_age_min_stability,
    check_sensor_age_min_freshness,
    check_sensor_age_min_coverage,
    check_sensor_age_min_consistency,
    check_sensor_age_min_risk,
    check_sensor_age_min_confidence,
    check_sensor_age_min_dependency,
    check_sensor_age_min_readiness,
    check_quality_flag_presence,
    check_quality_flag_range,
    check_quality_flag_stability,
    check_quality_flag_freshness,
    check_quality_flag_coverage,
    check_quality_flag_consistency,
    check_quality_flag_risk,
    check_quality_flag_confidence,
    check_quality_flag_dependency,
    check_quality_flag_readiness,
    check_upstream_delay_presence,
    check_upstream_delay_range,
    check_upstream_delay_stability,
    check_upstream_delay_freshness,
    check_upstream_delay_coverage,
    check_upstream_delay_consistency,
    check_upstream_delay_risk,
    check_upstream_delay_confidence,
    check_upstream_delay_dependency,
    check_upstream_delay_readiness,
    check_population_exposure_presence,
    check_population_exposure_range,
    check_population_exposure_stability,
    check_population_exposure_freshness,
    check_population_exposure_coverage,
    check_population_exposure_consistency,
    check_population_exposure_risk,
    check_population_exposure_confidence,
    check_population_exposure_dependency,
    check_population_exposure_readiness,
    check_delivery_channels_presence,
    check_delivery_channels_range,
    check_delivery_channels_stability,
    check_delivery_channels_freshness,
    check_delivery_channels_coverage,
    check_delivery_channels_consistency,
    check_delivery_channels_risk,
    check_delivery_channels_confidence,
    check_delivery_channels_dependency,
    check_delivery_channels_readiness,
    check_ack_rate_presence,
    check_ack_rate_range,
    check_ack_rate_stability,
    check_ack_rate_freshness,
    check_ack_rate_coverage,
    check_ack_rate_consistency,
    check_ack_rate_risk,
    check_ack_rate_confidence,
    check_ack_rate_dependency,
    check_ack_rate_readiness,
)

RULE_INDEX = {rule.__name__: rule for rule in RULES}

def evaluate(record: DomainRecord, context: Mapping[str, Any] | None = None) -> tuple[RuleResult, ...]:
    context = context or {}
    return tuple(rule(record, context) for rule in RULES)

def summarize(results: tuple[RuleResult, ...]) -> dict[str, Any]:
    if not results:
        return {'score': 0.0, 'passed': 0, 'failed': 0, 'critical': 0}
    return {'score': sum(item.score for item in results) / len(results),
            'passed': sum(item.passed for item in results),
            'failed': sum(not item.passed for item in results),
            'critical': sum(item.severity == 'critical' for item in results)}
