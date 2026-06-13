#!/usr/bin/env python3
"""Run one diagnosis wave over selected lanes in parallel using a lane registry."""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess  # nosec B404: intentional execution of configured leaves
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_wave_findings = importlib.import_module(
    "scripts._wave_findings" if __package__ else "_wave_findings"
)

# ── legacy hardcoded lanes ─────────────────────────────────────────────
# Kept as a fallback when neither --registry nor the committed default
# registry (scripts/wave_lanes.json) is available.
_LEGACY_LANES: dict[str, str] = {
    "code-health": "code-health-audit-pipeline/scripts/code_health_pipeline.py",
    "security": "security-audit/scripts/security_audit.py",
    "hygiene": "repo-hygiene-audit/scripts/repo_hygiene_audit.py",
    "docs": "docs-consistency-audit/scripts/docs_consistency_audit.py",
    "dependency": "dependency-audit/scripts/dependency_audit.py",
    "hotspot": "hotspot-audit/scripts/hotspot_audit.py",
}

_DEFAULT_REGISTRY = Path(__file__).resolve().parent / "wave_lanes.json"

DOC_EXCLUDES = ("audits", "dogfood", "plans", "superpowers")

# ── registry loader ────────────────────────────────────────────────────


def load_lanes(path: str | Path) -> dict[str, str]:
    """Load ordered lane names from a JSON registry.

    Expected schema::

        {"lanes": [
            {"name": "hygiene",
             "script": "repo-hygiene-audit/scripts/repo_hygiene_audit.py",
             "languages": ["*"]}
        ]}

    Returns ``{name: script_path}`` in registry order.
    """
    with open(path, encoding="utf-8") as fh:
        registry = json.load(fh)
    lanes: dict[str, str] = {}
    for entry in registry.get("lanes", []):
        lanes[entry["name"]] = entry["script"]
    return lanes


# ── internal helpers ────────────────────────────────────────────────────


@dataclass(frozen=True)
class _LaneContext:
    repo: Path
    out_root: Path
    source_prefixes: list[str]
    rev: str | None
    coverage_json: Path | None
    security_config: Path | None
    hotspot_config: Path | None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run diagnosis wave.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--skills-root", required=True, type=Path)
    parser.add_argument("--source-prefix", action="append", default=[])
    parser.add_argument("--coverage-json", type=Path)
    parser.add_argument("--rev")
    parser.add_argument("--security-config", type=Path)
    parser.add_argument("--hotspot-config", type=Path)
    parser.add_argument("--lanes")
    parser.add_argument("--registry", type=Path, help="Path to wave_lanes.json registry")
    return parser.parse_args(argv)


def _selected_lanes(
    raw_csv: str | None,
    lanes: dict[str, str],
) -> tuple[list[str], list[str]]:
    if not raw_csv:
        return list(lanes.keys()), []
    requested = [name.strip() for name in raw_csv.split(",") if name.strip()]
    unknown = sorted(set(requested) - set(lanes))
    if unknown:
        return [], unknown
    return [name for name in lanes if name in set(requested)], []


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
        ("README.md", "SKILL.md", "CHANGELOG.md")
        + ("references", "agents", "scripts")
    )
    docs_dir = repo / "docs"
    if docs_dir.exists():
        includes.extend(
            str(Path("docs") / child.name)
            for child in sorted(docs_dir.iterdir(), key=lambda p: p.name)
            if child.name not in DOC_EXCLUDES
        )
    return includes


def _append_flagged(cmd: list[str], flag: str, values: Iterable[str]) -> None:
    for value in values:
        cmd.extend([flag, value])


def _append_scope_args(
    cmd: list[str],
    lane: str,
    leaf: Path,
    context: _LaneContext,
) -> None:
    # exec lane: no extra args
    if lane == "exec":
        return

    # growth lane: --baseline-rev when rev is supplied;
    # auto-detect --config from repo-local growth_allowances.json
    if lane == "growth":
        if context.rev is not None:
            cmd.extend(["--baseline-rev", context.rev])
        growth_allowances = context.repo / "scripts" / "growth_allowances.json"
        if growth_allowances.exists():
            cmd.extend(["--config", str(growth_allowances)])
        return

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
    if lane == "security" and context.security_config is not None:
        cmd.extend(["--config", str(context.security_config)])


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
    return exit_code, _wave_findings.collect_lane_findings(lane_out, lane)


def _status_for_exit(exit_code: int, findings_count: int = 0) -> str:
    if exit_code == 0:
        return "ok"
    if exit_code == 1:
        return "findings"
    # exit_code >= 2: only "error" when no findings were produced;
    # a lane that exits 2 with parsed findings is a "findings" status.
    if findings_count > 0:
        return "findings"
    return "error"


# ── wave orchestration ──────────────────────────────────────────────────


def _run_wave(
    selected: list[str],
    lanes: dict[str, str],
    skills_root: Path,
    context: _LaneContext,
) -> tuple[int, dict[str, dict[str, Any]], list[dict[str, str]], dict[str, dict[str, Any]]]:
    """Run selected lanes in parallel, preserving registry order in outputs."""
    summary: dict[str, dict[str, Any]] = {}
    wave_findings: list[dict[str, str]] = []
    timings: dict[str, dict[str, Any]] = {}
    wave_exit = 0

    # --- partition: skip lanes whose leaf is missing or which should be skipped ---
    runnable: dict[str, Path] = {}
    for lane in selected:
        leaf = skills_root / lanes[lane]
        if not leaf.exists():
            summary[lane] = {"exit": 2, "status": "error", "findings": 0}
            wave_exit = 1
            continue
        # growth lane without --rev: skip entirely
        if lane == "growth" and context.rev is None:
            summary[lane] = {"exit": 0, "status": "skipped", "findings": 0}
            continue
        runnable[lane] = leaf

    # --- parallel execution ---
    if runnable:
        results: dict[str, tuple[int, list[dict[str, str]]]] = {}
        with ThreadPoolExecutor(max_workers=len(runnable)) as executor:
            future_to_lane: dict[Any, str] = {}
            start_times: dict[str, float] = {}
            for lane, leaf in runnable.items():
                start_times[lane] = time.time()
                future = executor.submit(_run_lane, lane, leaf, context)
                future_to_lane[future] = lane

            for future in as_completed(future_to_lane):
                lane = future_to_lane[future]
                end_ts = time.time()
                elapsed = round(end_ts - start_times[lane], 3)
                timings[lane] = {
                    "start": datetime.fromtimestamp(
                        start_times[lane], tz=timezone.utc
                    ).isoformat(),
                    "end": datetime.fromtimestamp(
                        end_ts, tz=timezone.utc
                    ).isoformat(),
                    "elapsed": elapsed,
                }
                try:
                    exit_code, findings = future.result()
                    results[lane] = (exit_code, findings)
                except Exception:
                    results[lane] = (2, [])

        # Build summary and findings in *registry order* (deterministic).
        for lane in selected:
            if lane in results:
                exit_code, findings = results[lane]
                summary[lane] = {
                    "exit": exit_code,
                    "status": _status_for_exit(exit_code, len(findings)),
                    "findings": len(findings),
                }
                wave_findings.extend(findings)
                if exit_code >= 2 and not findings:
                    wave_exit = 1

    return wave_exit, summary, wave_findings, timings


# ── output ──────────────────────────────────────────────────────────────


def _write_wave_outputs(
    out_root: Path,
    wave_exit: int,
    summary: dict[str, dict[str, Any]],
    wave_findings: list[dict[str, str]],
    timings: dict[str, dict[str, Any]],
) -> int:
    summary_path = out_root / "wave_summary.json"
    findings_path = out_root / "wave_findings.json"
    timings_path = out_root / "wave_timings.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    findings_path.write_text(json.dumps(wave_findings, indent=2), encoding="utf-8")
    timings_path.write_text(json.dumps(timings, indent=2), encoding="utf-8")
    payload = {"status": "ok" if wave_exit == 0 else "error", "summary": summary}
    print(json.dumps(payload, sort_keys=True))
    return wave_exit


# ── entry point ─────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.registry:
        loaded = load_lanes(args.registry)
    elif _DEFAULT_REGISTRY.exists():
        loaded = load_lanes(_DEFAULT_REGISTRY)
    else:
        loaded = dict(_LEGACY_LANES)
    selected, unknown = _selected_lanes(args.lanes, loaded)
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
        args.security_config,
        args.hotspot_config,
    )
    run = _run_wave(selected, loaded, args.skills_root, context)
    return _write_wave_outputs(args.out_dir, *run)


if __name__ == "__main__":
    raise SystemExit(main())
