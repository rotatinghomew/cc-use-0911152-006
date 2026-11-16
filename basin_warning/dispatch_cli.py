from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from basin_warning.command_center import Application, run, verify
from basin_warning.observations.hydro_event import DomainRecord, records_from_fixture
from basin_warning.replay.replay_engine import select_evidence_backed
from basin_warning.replay.rule_package import RulePackage
from basin_warning.replay.trial_report import export_replay_bundle, verify_replay_bundle


def _load_labels(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("labels file must be a JSON object keyed by record_id")
    return value


def _load_candidates(path: str | Path) -> list[RulePackage]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or not value:
        raise ValueError("candidate file must contain a package object or a list of packages")
    return [RulePackage.from_dict(item) for item in value]


def _load_single_package(path: str | Path) -> RulePackage:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(value, list):
        if len(value) != 1:
            raise ValueError("this command expects exactly one rule package object")
        value = value[0]
    return RulePackage.from_dict(value)


def _load_records(path: str | Path) -> list[DomainRecord]:
    fixture = json.loads(Path(path).read_text(encoding="utf-8"))
    return records_from_fixture(fixture)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog='basin_warning', description='跨境流域临灾数据融合与预警复盘系统')
    commands = root.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--fixture", required=True)
    execute.add_argument("--database", required=True)
    execute.add_argument("--output", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--database", required=True)
    check.add_argument("--output", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--database", required=True)

    replay = commands.add_parser("replay", help="shadow replay of alternative rule packages")
    replay.add_argument("--fixture", required=True)
    replay.add_argument("--labels", required=True)
    replay.add_argument("--candidates", required=True)
    replay.add_argument("--database", required=True)
    replay.add_argument("--trial-database")
    replay.add_argument("--output")

    reviews = commands.add_parser("review", help="list candidate enablement reviews")
    reviews.add_argument("--database", required=True)
    reviews.add_argument("--trial-database")
    reviews.add_argument("--status")

    submit = commands.add_parser("submit-review", help="send an evidence-backed candidate to review")
    submit.add_argument("--database", required=True)
    submit.add_argument("--trial-database")
    submit.add_argument("--package", required=True)
    submit.add_argument("--replay-id", required=True)
    submit.add_argument("--actor", required=True)
    submit.add_argument("--rationale", required=True)

    decide_cmd = commands.add_parser("decide-review", help="approve or reject a candidate review")
    decide_cmd.add_argument("--database", required=True)
    decide_cmd.add_argument("--trial-database")
    decide_cmd.add_argument("--review-id", required=True)
    decide_cmd.add_argument("--approve", action="store_true")
    decide_cmd.add_argument("--reject", action="store_true")
    decide_cmd.add_argument("--actor", required=True)
    decide_cmd.add_argument("--rationale", required=True)

    enable = commands.add_parser("enable", help="enable an approved package after live verification")
    enable.add_argument("--database", required=True)
    enable.add_argument("--trial-database")
    enable.add_argument("--package", required=True)
    enable.add_argument("--actor", required=True)

    withdraw = commands.add_parser("withdraw", help="withdraw a candidate before or after review")
    withdraw.add_argument("--database", required=True)
    withdraw.add_argument("--trial-database")
    withdraw.add_argument("--package", required=True)
    withdraw.add_argument("--actor", required=True)
    withdraw.add_argument("--reason", required=True)

    correct = commands.add_parser("correct-observation", help="register corrected observation evidence")
    correct.add_argument("--database", required=True)
    correct.add_argument("--trial-database")
    correct.add_argument("--record", required=True)
    correct.add_argument("--reason", required=True)

    verify_trial = commands.add_parser("verify-trial", help="verify exported shadow trial bundle")
    verify_trial.add_argument("--output", required=True)
    return root


def _application(args: argparse.Namespace) -> Application:
    return Application(args.database, trial_database=getattr(args, "trial_database", None))


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "run":
        result = run(args.fixture, args.database, args.output)
    elif args.command == "verify":
        result = verify(args.database, args.output)
    elif args.command == "inspect":
        result = Application(args.database).inspect()
    elif args.command == "replay":
        application = _application(args)
        records = _load_records(args.fixture)
        labels = _load_labels(args.labels)
        candidates = _load_candidates(args.candidates)
        reports = application.run_replay_portfolio(records, labels, candidates)
        result = {
            "replays": [
                {
                    "replay_id": report.replay_id,
                    "candidate": report.candidate_package["package_id"],
                    "eligible": report.eligibility.eligible,
                    "blocking_reasons": report.eligibility.blocking_reasons,
                    "baseline_metrics": report.baseline_metrics.as_dict(),
                    "candidate_metrics": report.candidate_metrics.as_dict(),
                }
                for report in reports
            ],
            "evidence_backed_choice": (
                select_evidence_backed(reports).replay_id
                if select_evidence_backed(reports) else None
            ),
        }
        if args.output:
            for report in reports:
                bundle = export_replay_bundle(
                    Path(args.output) / report.replay_id,
                    report,
                    application.trial_store.list_reviews(),
                    application.trial_store.list_corrections(),
                )
                result.setdefault("bundles", {})[report.replay_id] = bundle
    elif args.command == "review":
        application = _application(args)
        result = {"reviews": application.trial_store.list_reviews(args.status),
                  "active_basis": application.trial_store.active_basis(),
                  "trial_chain_errors": application.trial_store.verify_trial_chain()}
    elif args.command == "submit-review":
        application = _application(args)
        package = _load_single_package(args.package)
        review_id = application.submit_candidate(
            package, args.replay_id, args.actor, args.rationale
        )
        result = {"review_id": review_id, "status": "submitted"}
    elif args.command == "decide-review":
        if args.approve == args.reject:
            raise SystemExit("choose exactly one of --approve or --reject")
        application = _application(args)
        result = application.decide_candidate_review(
            args.review_id, args.approve, args.actor, args.rationale
        )
    elif args.command == "enable":
        application = _application(args)
        package = _load_single_package(args.package)
        result = application.enable_candidate(package, args.actor)
    elif args.command == "withdraw":
        application = _application(args)
        package = _load_single_package(args.package)
        application.withdraw_candidate(package, args.actor, args.reason)
        result = {"package_id": package.package_id, "version": package.version, "status": "withdrawn"}
    elif args.command == "correct-observation":
        application = _application(args)
        corrected = DomainRecord.from_dict(json.loads(Path(args.record).read_text(encoding="utf-8")))
        result = application.record_observation_correction(corrected, args.reason)
    elif args.command == "verify-trial":
        errors = verify_replay_bundle(args.output)
        result = {"ok": not errors, "errors": errors}
    else:  # pragma: no cover - argparse enforces the command set
        raise SystemExit(f"unknown command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
