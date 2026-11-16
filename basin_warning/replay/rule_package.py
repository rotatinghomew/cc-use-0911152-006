"""Versioned rule packages for shadow replay and alternative-rule comparison.

A rule package never mutates the live engine.  It is an immutable, fingerprinted
description of the context overrides (rule thresholds, guard floors, engine
thresholds) and the outcomes that count as an alert during historical replay.
The baseline package captures the rules currently serving production so that
every candidate can be compared against the same evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from basin_warning.observations.hydro_event import (
    ContractError,
    canonical_json,
    finite_number,
    identifier,
    stable_hash,
)

BASELINE_PACKAGE_ID = "baseline-rule-package"
BASELINE_VERSION = 1
KNOWN_OUTCOMES = ("approve", "review", "hold", "reject")
DEFAULT_ALERT_OUTCOMES = ("approve", "hold")
_ENGINE_KEYS = {"transition_threshold", "approve_threshold", "review_threshold"}
_GUARD_FLOOR_RE = re.compile(r"^guard_[a-z0-9_]+_floor$")
_METRIC_OFFSET_RE = re.compile(r"^metric_[a-z0-9_]+_offset$")
_WEIGHT_RE = re.compile(r"^[a-z0-9_]+_weight$")
_RULE_THRESHOLD_RE = re.compile(r"^check_[a-z0-9_]+_threshold$")


def _validate_context_key(key: str) -> None:
    if key in _ENGINE_KEYS:
        return
    if _GUARD_FLOOR_RE.match(key) or _METRIC_OFFSET_RE.match(key):
        return
    if _WEIGHT_RE.match(key) or _RULE_THRESHOLD_RE.match(key):
        return
    raise ContractError(f"unknown rule tuning key in package: {key}")


def _validate_overrides(overrides: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(overrides, Mapping):
        raise ContractError("rule package context_overrides must be an object")
    clean: dict[str, float] = {}
    for raw_key, raw_value in overrides.items():
        key = identifier(raw_key)
        _validate_context_key(key)
        clean[key] = finite_number(raw_value)
    return dict(sorted(clean.items()))


def _validate_outcomes(outcomes: Sequence[str]) -> tuple[str, ...]:
    if not outcomes:
        raise ContractError("rule package must declare at least one alert outcome")
    normalized = tuple(identifier(value) for value in outcomes)
    unknown = [value for value in normalized if value not in KNOWN_OUTCOMES]
    if unknown:
        raise ContractError(f"unknown alert outcomes: {', '.join(unknown)}")
    if len(set(normalized)) != len(normalized):
        raise ContractError("duplicate alert outcomes in rule package")
    return normalized


def _validate_scope(scope: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(scope, Mapping):
        raise ContractError("rule package scope must be an object")
    station_ids = scope.get("station_ids", [])
    event_types = scope.get("event_types", [])
    if not isinstance(station_ids, list) or not isinstance(event_types, list):
        raise ContractError("scope station_ids and event_types must be lists")
    clean_stations = sorted({identifier(value) for value in station_ids})
    clean_types = sorted({identifier(value) for value in event_types})
    return {"station_ids": clean_stations, "event_types": clean_types}


@dataclass(frozen=True)
class RulePackage:
    """Immutable alternative rule set identified by package_id + version."""

    package_id: str
    version: int
    context_overrides: dict[str, float] = field(default_factory=dict)
    alert_outcomes: tuple[str, ...] = DEFAULT_ALERT_OUTCOMES
    description: str = ""
    scope: dict[str, Any] = field(default_factory=lambda: {"station_ids": [], "event_types": []})

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_id", identifier(self.package_id))
        if not isinstance(self.version, int) or self.version < 1:
            raise ContractError("rule package version must be a positive integer")
        object.__setattr__(self, "version", self.version)
        object.__setattr__(self, "context_overrides", _validate_overrides(self.context_overrides))
        object.__setattr__(self, "alert_outcomes", _validate_outcomes(self.alert_outcomes))
        object.__setattr__(self, "description", " ".join(str(self.description or "").split()))
        object.__setattr__(self, "scope", _validate_scope(self.scope))

    @property
    def content(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "version": self.version,
            "description": self.description,
            "context_overrides": self.context_overrides,
            "alert_outcomes": list(self.alert_outcomes),
            "scope": self.scope,
        }

    @property
    def fingerprint(self) -> str:
        return stable_hash(self.content)

    def as_dict(self) -> dict[str, Any]:
        return self.content | {"fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RulePackage":
        if not isinstance(value, Mapping):
            raise ContractError("rule package must be an object")
        package_id = value.get("package_id")
        if not package_id:
            raise ContractError("rule package requires package_id")
        return cls(
            package_id=str(package_id),
            version=int(value.get("version", 1)),
            context_overrides=dict(value.get("context_overrides") or {}),
            alert_outcomes=tuple(value.get("alert_outcomes") or DEFAULT_ALERT_OUTCOMES),
            description=str(value.get("description") or ""),
            scope=dict(value.get("scope") or {}),
        )

    def applies_to(self, station_id: str | None, event_type: str | None) -> bool:
        """Empty scope means the package applies fleet-wide."""
        stations = self.scope.get("station_ids") or []
        event_types = self.scope.get("event_types") or []
        station_ok = not stations or (station_id is not None and identifier(station_id) in stations)
        type_ok = not event_types or (event_type is not None and identifier(event_type) in event_types)
        return station_ok and type_ok

    def basis(self) -> dict[str, Any]:
        """Minimal rule-basis stamp carried by decisions and notices."""
        return {
            "package_id": self.package_id,
            "version": self.version,
            "fingerprint": self.fingerprint,
        }


def baseline_package() -> RulePackage:
    """The rules currently serving production: no overrides, default semantics."""
    return RulePackage(
        package_id=BASELINE_PACKAGE_ID,
        version=BASELINE_VERSION,
        description="production baseline rule package captured for shadow replay",
    )


def package_from_json_text(text: str) -> RulePackage:
    import json

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError("rule package JSON is invalid") from exc
    return RulePackage.from_dict(value)


def canonical_packages(packages: Sequence[RulePackage]) -> str:
    return canonical_json([package.content for package in packages])
