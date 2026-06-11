#!/usr/bin/env python3
"""Run one diagnosis wave over selected lanes in sequence."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404: intentional execution of configured leaves
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LANES = {
    "code-health": "code-health-audit-pipeline/scripts/code_health_pipeline.py",
    "security": "security-audit/scripts/security_audit.py",
    "hygiene": "repo-hygiene-audit/scripts/repo_hygiene_audit.py",
    "docs": "docs-consistency-audit/scripts/docs_consistency_audit.py",
    "dependency": "dependency-audit/scripts/dependency_audit.py",
    "hotspot": "hotspot-audit/scripts/hotspot_audit.py",
}
DOC_EXCLUDES = ("audits", "dogfood", "plans", "superpowers")


@dataclass(frozen=True)
class _LaneContext:
    repo: Path
    out_root: Path
    source_prefixes: list[str]
    rev: str | None
    coverage_json: Path | None
    hotspot_config: Path | None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run diagnosis wave.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--skills-root", required=True, type=Path)
    parser.add_argument("--source-prefix", action="append", default=[])
    parser.add_argument("--coverage-json", type=Path)
    parser.add_argument("--rev")
    parser.add_argument("--hotspot-config", type=Path)
    parser.add_argument("--lanes")
    return parser.parse_args(argv)


def _selected_lanes(raw_csv: str | None) -> tuple[list[str], list[str]]:
    if not raw_csv:
        return list(LANES.keys()), []
    requested = [name.strip() for name in raw_csv.split(",") if name.strip()]
    unknown = sorted(set(requested) - set(LANES))
    if unknown:
        return [], unknown
    return [name for name in LANES if name in set(requested)], []


def _leaf_supports_exclude_prefix(leaf: Path) -> bool:
    try:
        cmd = [sys.executable, str(leaf), "--help"]
        proc = subprocess.run(  # nosec B603: shell=False and trusted leaf path
            cmd, check=False, capture_output=True, text=True
        )
    except OSError:
        return False
    help_text = f"{proc.stdout or ''}{proc.stderr or ''}"
    return "--exclude-prefix" in help_text


def _doc_prefixes(repo: Path) -> list[str]:
    includes = list(
        ("README.md", "SKILL.md", "CHANGELOG.md") + ("references", "agents", "scripts")
    )
    docs_dir = repo / "docs"
    if docs_dir.exists():
        includes.extend(
            str(Path("docs") / child.name)
            for child in sorted(docs_dir.iterdir(), key=lambda p: p.name)
            if child.name not in DOC_EXCLUDES
        )
    return includes


def _string_value(value: Any, fallback: Any = "") -> str:
    if isinstance(value, str):
        return value
    return fallback if isinstance(fallback, str) else ""


def _normalize_finding(finding: dict[str, Any], lane: str) -> dict[str, str]:
    location = finding.get("location")
    if not isinstance(location, dict):
        location = {}
    metric = finding.get("metric")
    if isinstance(metric, dict):
        metric = metric.get("name")
    if metric is None:
        metric = finding.get("signal", "")
    return {
        "leaf": _string_value(finding.get("leaf"), lane),
        "path": _string_value(finding.get("path"), location.get("path", "")),
        "symbol": _string_value(finding.get("symbol"), location.get("symbol", "")),
        "metric": "" if metric is None else str(metric),
    }


def _read_findings_file(path: Path, lane: str) -> list[dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("findings", [])
    if not isinstance(payload, list):
        return []
    return [
        _normalize_finding(item, lane) for item in payload if isinstance(item, dict)
    ]


def _collect_lane_findings(lane_dir: Path, lane: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for finding_path in sorted(lane_dir.glob("*_findings.json")):
        findings.extend(_read_findings_file(finding_path, lane))
    code_health_summary = lane_dir / "code_health_summary.json"
    if code_health_summary.exists():
        findings.extend(_read_findings_file(code_health_summary, lane))
    return findings


def _append_flagged(cmd: list[str], flag: str, values: Iterable[str]) -> None:
    for value in values:
        cmd.extend([flag, value])


def _append_scope_args(
    cmd: list[str],
    lane: str,
    leaf: Path,
    context: _LaneContext,
) -> None:
    if lane in {"code-health", "security", "dependency"}:
        _append_flagged(cmd, "--source-prefix", context.source_prefixes)
    elif lane == "docs":
        if _leaf_supports_exclude_prefix(leaf):
            cmd.extend(["--source-prefix", "docs"])
            excludes = (f"docs/{p}" for p in DOC_EXCLUDES)
            _append_flagged(cmd, "--exclude-prefix", excludes)
        else:
            _append_flagged(cmd, "--source-prefix", _doc_prefixes(context.repo))
    elif lane == "hotspot":
        if context.rev is not None:
            cmd.extend(["--rev", context.rev])
        if context.hotspot_config is not None:
            cmd.extend(["--config", str(context.hotspot_config)])


def _run_lane(
    lane: str,
    leaf: Path,
    context: _LaneContext,
) -> tuple[int, list[dict[str, str]]]:
    lane_out = context.out_root / lane
    lane_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(leaf),
        "--root",
        str(context.repo),
        "--out-dir",
        str(lane_out),
    ]
    _append_scope_args(cmd, lane, leaf, context)
    if lane == "code-health" and context.coverage_json is not None:
        cmd.extend(["--coverage-json", str(context.coverage_json)])

    try:
        exit_code = subprocess.run(  # nosec B603: shell=False
            cmd, check=False, capture_output=True, text=True
        ).returncode
    except OSError:
        exit_code = 2
    return exit_code, _collect_lane_findings(lane_out, lane)


def _status_for_exit(exit_code: int) -> str:
    return {0: "ok", 1: "findings"}.get(exit_code, "error")


def _run_wave(
    selected: list[str],
    skills_root: Path,
    context: _LaneContext,
) -> tuple[int, dict[str, dict[str, Any]], list[dict[str, str]]]:
    summary: dict[str, dict[str, Any]] = {}
    wave_findings: list[dict[str, str]] = []
    wave_exit = 0

    for lane in selected:
        leaf = skills_root / LANES[lane]
        if not leaf.exists():
            summary[lane] = {"exit": 2, "status": "error", "findings": 0}
            wave_exit = 1
            continue

        exit_code, findings = _run_lane(lane, leaf, context)
        summary[lane] = {
            "exit": exit_code,
            "status": _status_for_exit(exit_code),
            "findings": len(findings),
        }
        wave_findings.extend(findings)
        if exit_code >= 2:
            wave_exit = 1

    return wave_exit, summary, wave_findings


def _write_wave_outputs(
    out_root: Path,
    wave_exit: int,
    summary: dict[str, dict[str, Any]],
    wave_findings: list[dict[str, str]],
) -> int:
    summary_path = out_root / "wave_summary.json"
    findings_path = out_root / "wave_findings.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    findings_path.write_text(json.dumps(wave_findings, indent=2), encoding="utf-8")
    payload = {"status": "ok" if wave_exit == 0 else "error", "summary": summary}
    print(json.dumps(payload, sort_keys=True))
    return wave_exit


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    selected, unknown = _selected_lanes(args.lanes)
    if unknown:
        payload = {"status": "error", "error": "Unknown lane(s)", "lanes": unknown}
        print(json.dumps(payload, sort_keys=True))
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    context = _LaneContext(
        args.repo,
        args.out_dir,
        args.source_prefix,
        args.rev,
        args.coverage_json,
        args.hotspot_config,
    )
    run = _run_wave(selected, args.skills_root, context)
    return _write_wave_outputs(args.out_dir, *run)


if __name__ == "__main__":
    raise SystemExit(main())
