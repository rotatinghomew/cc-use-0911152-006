"""Hash-verified export of shadow replay and review artifacts.

Reports are written outside the live bundle directory so trial activity can be
archived and reviewed independently.  Every JSON artifact is content-hashed and
the manifest pins those hashes; verification detects any post-hoc tampering,
which the post-incident review relies on when explaining a withdrawal.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from basin_warning.observations.hydro_event import stable_hash, utc_now
from basin_warning.replay.replay_engine import ReplayReport


def ensure_output(path: str | Path) -> Path:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_json(path: Path, value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(body + "\n", encoding="utf-8")
    return stable_hash(value)


def export_replay_bundle(
    output: str | Path,
    report: ReplayReport,
    review_rows: Sequence[Mapping[str, Any]] | None = None,
    correction_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    root = ensure_output(output)
    report_body = report.as_dict()
    expected_report_hash = report_body["fingerprint"]
    # The fingerprint covers the body excluding the fingerprint field itself.
    report_hash = stable_hash({key: value for key, value in report_body.items() if key != "fingerprint"})
    write_json(root / "replay-report.json", report_body)
    if report_hash != expected_report_hash:
        raise ValueError("exported report fingerprint mismatch")

    stations = [group.as_dict() for group in report.station_comparisons]
    event_types = [group.as_dict() for group in report.event_type_comparisons]
    contributions = [item.as_dict() for item in report.rule_contributions]
    station_hash = write_json(root / "station-comparison.json", stations)
    event_type_hash = write_json(root / "event-type-comparison.json", event_types)
    contribution_hash = write_json(root / "rule-contributions.json", contributions)

    summary = {
        "replay_id": report.replay_id,
        "candidate_package": report.candidate_package,
        "baseline_package": report.baseline_package,
        "generated_at": utc_now(),
        "baseline_metrics": report.baseline_metrics.as_dict(),
        "candidate_metrics": report.candidate_metrics.as_dict(),
        "eligibility": report.eligibility.as_dict(),
        "observation_count": len(report.observation_fingerprints),
        "rule_flip_count": len(report.rule_flips),
        "report_hash": report_hash,
    }
    summary_hash = write_json(root / "trial-summary.json", summary)
    review_hash = write_json(root / "reviews.json", list(review_rows or []))
    correction_hash = write_json(root / "observation-corrections.json", list(correction_rows or []))

    manifest = {
        "files": {
            "replay-report.json": report_hash,
            "trial-summary.json": summary_hash,
            "station-comparison.json": station_hash,
            "event-type-comparison.json": event_type_hash,
            "rule-contributions.json": contribution_hash,
            "reviews.json": review_hash,
            "observation-corrections.json": correction_hash,
        },
        "created_at": utc_now(),
    }
    manifest["manifest_hash"] = stable_hash(manifest)
    write_json(root / "trial-manifest.json", manifest)
    return manifest


def verify_replay_bundle(output: str | Path) -> list[str]:
    root = Path(output)
    manifest_path = root / "trial-manifest.json"
    if not manifest_path.is_file():
        return ["trial-manifest.json is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest_hash = manifest.pop("manifest_hash", "")
    errors: list[str] = []
    if stable_hash(manifest) != expected_manifest_hash:
        errors.append("trial manifest hash mismatch")
    for name, expected in manifest.get("files", {}).items():
        path = root / name
        if not path.is_file():
            errors.append(f"{name} is missing")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        # The replay report fingerprint excludes the fingerprint field itself.
        if name == "replay-report.json":
            value = {key: item for key, item in value.items() if key != "fingerprint"}
        if stable_hash(value) != expected:
            errors.append(f"{name} hash mismatch")
    return errors
