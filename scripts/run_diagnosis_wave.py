#!/usr/bin/env python3
"""Run one diagnosis wave over selected lanes in sequence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


LANES = {
    "code-health": (
        "code-health-audit-pipeline/scripts/code_health_pipeline.py",
        "prefixes",
    ),
    "security": ("security-audit/scripts/security_audit.py", "prefixes"),
    "hygiene": ("repo-hygiene-audit/scripts/repo_hygiene_audit.py", "none"),
    "docs": (
        "docs-consistency-audit/scripts/docs_consistency_audit.py",
        "living-docs",
    ),
    "dependency": ("dependency-audit/scripts/dependency_audit.py", "prefixes"),
    "hotspot": ("hotspot-audit/scripts/hotspot_audit.py", "rev"),
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run diagnosis wave.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--skills-root", required=True, type=Path)
    parser.add_argument("--source-prefix", action="append", default=[])
    parser.add_argument("--coverage-json", type=Path)
    parser.add_argument("--rev")
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
        proc = subprocess.run(
            [sys.executable, str(leaf), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return "--exclude-prefix" in (proc.stdout or "") or "--exclude-prefix" in (
        proc.stderr or ""
    )


def _doc_prefixes(repo: Path) -> list[str]:
    includes = ["README.md", "SKILL.md", "CHANGELOG.md", "references", "agents", "scripts"]
    docs_dir = repo / "docs"
    if docs_dir.exists():
        for child in sorted(docs_dir.iterdir(), key=lambda p: p.name):
            if child.name in {"audits", "dogfood", "plans"}:
                continue
            includes.append(str(Path("docs") / child.name))
    return includes


def _normalize_finding(finding: dict[str, Any], lane: str) -> dict[str, str]:
    location = finding.get("location") if isinstance(finding.get("location"), dict) else {}
    metric = finding.get("metric")
    if isinstance(metric, dict):
        metric = metric.get("name")
    if metric is None:
        metric = finding.get("signal", "")
    return {
        "leaf": finding.get("leaf") or lane,
        "path": finding.get("path") or location.get("path") or "",
        "symbol": location.get("symbol") or finding.get("symbol") or "",
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
    return [_normalize_finding(item, lane) for item in payload if isinstance(item, dict)]


def _collect_lane_findings(lane_dir: Path, lane: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for finding_path in sorted(lane_dir.glob("*_findings.json")):
        findings.extend(_read_findings_file(finding_path, lane))
    code_health_summary = lane_dir / "code_health_summary.json"
    if code_health_summary.exists():
        findings.extend(_read_findings_file(code_health_summary, lane))
    return findings


def _run_lane(
    lane: str,
    path: str,
    args: argparse.Namespace,
    out_root: Path,
    repo: Path,
    source_prefixes: list[str],
) -> tuple[int, list[dict[str, str]]]:
    lane_out = out_root / lane
    lane_out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, path, "--root", str(repo), "--out-dir", str(lane_out)]

    if lane in {"code-health", "security", "dependency"}:
        for source_prefix in source_prefixes:
            cmd.extend(["--source-prefix", source_prefix])
    elif lane == "docs":
        supports = _leaf_supports_exclude_prefix(Path(path))
        if supports:
            cmd.extend(["--source-prefix", "docs"])
            for prefix in ["docs/audits", "docs/dogfood", "docs/plans"]:
                cmd.extend(["--exclude-prefix", prefix])
        else:
            for prefix in _doc_prefixes(repo):
                cmd.extend(["--source-prefix", prefix])
    elif lane == "hotspot" and args.rev:
        cmd.extend(["--rev", args.rev])
    if lane == "code-health" and args.coverage_json is not None:
        cmd.extend(["--coverage-json", str(args.coverage_json)])

    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        exit_code = proc.returncode
    except OSError:
        return 2, []

    return exit_code, _collect_lane_findings(lane_out, lane)


def _status_for_exit(exit_code: int) -> str:
    if exit_code == 0:
        return "ok"
    if exit_code == 1:
        return "findings"
    return "error"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    selected, unknown = _selected_lanes(args.lanes)
    if unknown:
        print(
            json.dumps(
                {"status": "error", "error": "Unknown lane(s)", "lanes": unknown},
                sort_keys=True,
            )
        )
        return 2

    repo = args.repo
    out_root = args.out_dir
    out_root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, dict[str, Any]] = {}
    wave_findings: list[dict[str, str]] = []
    wave_exit = 0

    for lane in selected:
        path_rel, _scope = LANES[lane]
        leaf = args.skills_root / path_rel
        if not leaf.exists():
            summary[lane] = {"exit": 2, "status": "error", "findings": 0}
            wave_exit = 1
            continue

        exit_code, findings = _run_lane(
            lane,
            str(leaf),
            args,
            out_root,
            repo,
            args.source_prefix,
        )
        summary[lane] = {
            "exit": exit_code,
            "status": _status_for_exit(exit_code),
            "findings": len(findings),
        }
        wave_findings.extend(findings)

        if exit_code >= 2:
            wave_exit = 1

    (out_root / "wave_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (out_root / "wave_findings.json").write_text(
        json.dumps(wave_findings, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": "ok" if wave_exit == 0 else "error", "summary": summary},
            sort_keys=True,
        )
    )
    return wave_exit


if __name__ == "__main__":
    raise SystemExit(main())
