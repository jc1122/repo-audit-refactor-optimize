#!/usr/bin/env python3
"""Validate a run report directory against schema 1 or 2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEYS = [
    "schema_version",
    "repo_root",
    "started_utc",
    "finished_utc",
    "orchestrator_skill_version",
    "lanes",
    "findings_totals",
    "backlog",
    "batches",
    "verification",
    "warnings",
]

BACKLOG = {
    1: {"accepted", "deferred", "coverage_gated"},
    2: {"accepted", "deferred", "coverage_gated", "wont_fix"},
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate run-report schema.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--schema", type=int, choices=[1, 2], default=2)
    return parser.parse_args(argv)


def _json_verdict(passed: bool, defects: list[str] | None = None) -> int:
    if passed:
        print(json.dumps({"status": "pass"}))
        return 0
    print(json.dumps({"status": "fail", "defects": defects or []}))
    return 1


def _run_validation(run_dir: Path, requested_schema: int) -> int:
    defects: list[str] = []

    report_path = run_dir / "run_report.json"
    md_path = run_dir / "run_report.md"
    if not report_path.exists():
        defects.append(f"Missing required file: {report_path}")
    if not md_path.exists():
        defects.append(f"Missing required file: {md_path}")
    if defects:
        return _json_verdict(False, defects)

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _json_verdict(False, [f"run_report.json is invalid JSON: {exc}"])
    except OSError as exc:
        return _json_verdict(False, [f"Failed reading run_report.json: {exc}"])

    if not isinstance(payload, dict):
        return _json_verdict(False, ["run_report.json must be a JSON object"])

    for key in KEYS:
        if key not in payload:
            defects.append(f"Missing required top-level key: {key}")

    payload_schema = payload.get("schema_version")
    if payload_schema != requested_schema:
        defects.append(
            f"schema_version mismatch: {payload_schema!r} != expected {requested_schema}"
        )

    if not defects:
        backlog = payload["backlog"]
        if not isinstance(backlog, dict):
            defects.append("Invalid type for 'backlog': expected object")
        else:
            required = BACKLOG.get(requested_schema, set())
            for key in sorted(required - set(backlog)):
                defects.append(f"Missing required backlog key: {key}")

    return _json_verdict(not defects, defects)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return _run_validation(args.run_dir, args.schema)


if __name__ == "__main__":
    sys.exit(main())
