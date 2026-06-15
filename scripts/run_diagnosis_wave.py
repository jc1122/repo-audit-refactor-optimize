#!/usr/bin/env python3
"""Run one diagnosis wave over selected lanes in parallel using a lane registry."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess  # nosec B404: intentional execution of configured leaves
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts import _accept  # static binding for the type checker only

_wave_findings = importlib.import_module(
    "scripts._wave_findings" if __package__ else "_wave_findings"
)
_accept = importlib.import_module(
    "scripts._accept" if __package__ else "_accept"
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

DEFAULT_EXCLUDES = ("tests", "fixtures")

# Lanes whose findings are scoped to source via --source-prefix. The registry
# mirrors this via "source_scoped": true; the gate-integrity test asserts parity,
# so adding a 10th scopable lane without scoping it fails CI (#11).
SOURCE_SCOPED_LANES = {"code-health", "security", "dependency", "perf-smell"}

# Runner version + capability surface (#8). __version__ is kept equal to the
# SKILL.md version by check_release.py; downstream repos assert the pinned
# runner advertises the capabilities they require before trusting its gate.
__version__ = "0.11.2"
CAPABILITIES = ("lane-error-gate", "metric-ceiling", "lane-timeout")


def _lane_timeout() -> int:
    """Per-lane wall-clock budget (seconds); env-overridable for tests/CI."""
    return int(os.environ.get("WAVE_LANE_TIMEOUT", "600"))


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
    lanes: dict[str, str] = {
        entry["name"]: entry["script"] for entry in registry.get("lanes", [])
    }
    return lanes


# ── internal helpers ────────────────────────────────────────────────────


@dataclass(frozen=True)
class _LaneContext:
    repo: Path
    out_root: Path
    source_prefixes: list[str]
    exclude_prefixes: list[str]
    rev: str | None
    coverage_json: Path | None
    security_config: Path | None
    hotspot_config: Path | None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run diagnosis wave.")
    parser.add_argument(
        "--capabilities", action="store_true",
        help="Print {version, capabilities} JSON and exit (no wave run)",
    )
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--source-prefix", action="append", default=[])
    parser.add_argument("--exclude-prefix", action="append", default=[])
    parser.add_argument("--coverage-json", type=Path)
    parser.add_argument("--rev")
    parser.add_argument("--security-config", type=Path)
    parser.add_argument("--hotspot-config", type=Path)
    parser.add_argument("--lanes")
    parser.add_argument(
        "--registry", type=Path, help="Path to wave_lanes.json registry"
    )
    parser.add_argument(
        "--baseline", type=Path, help="Accepted-residuals JSON to suppress"
    )
    parser.add_argument(
        "--accept", type=Path,
        help="Extra acceptance policy file merged with <repo>/.repo-audit/accept.json",
    )
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
        cmd = (sys.executable, str(leaf), "--help")
        proc = subprocess.run(  # nosec B603: shell=False and trusted leaf path
            cmd, check=False, capture_output=True, text=True,
            timeout=_lane_timeout(),
        )
    except (OSError, subprocess.TimeoutExpired):
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


def _append_flagged(cmd: list[str], flag: str, values: Iterable[str]) -> None:
    for value in values:
        cmd.extend([flag, value])


def _effective_excludes(
    source_prefixes: list[str], exclude_prefixes: list[str]
) -> list[str]:
    """Default exclusions when scoping is implicit; explicit scoping overrides.

    Explicit --exclude-prefix always wins. Otherwise, when no --source-prefix is
    given the wave scopes nothing positively, so it excludes tests/fixtures by
    default; an explicit --source-prefix means the caller is scoping deliberately,
    so no default exclusion is added.
    """
    if exclude_prefixes:
        return list(exclude_prefixes)
    if source_prefixes:
        return []
    return list(DEFAULT_EXCLUDES)


def _audit_scope_args(
    source_prefixes: list[str], exclude_prefixes: list[str], supports_exclude: bool
) -> list[str]:
    """Scope flags for the source-auditing lanes (code-health/security/dependency)."""
    args: list[str] = []
    for prefix in source_prefixes:
        args.extend(["--source-prefix", prefix])
    if supports_exclude:
        for prefix in exclude_prefixes:
            args.extend(["--exclude-prefix", prefix])
    return args


def _add_growth_args(cmd: list[str], context: _LaneContext) -> None:
    """Append growth-lane flags: --baseline-rev and auto-detected --config."""
    if context.rev is not None:
        cmd.extend(["--baseline-rev", context.rev])
    growth_allowances = context.repo / "scripts" / "growth_allowances.json"
    if growth_allowances.exists():
        cmd.extend(["--config", str(growth_allowances)])


def _add_docs_args(cmd: list[str], leaf: Path, context: _LaneContext) -> None:
    """Append docs-lane flags: source/exclude prefix depending on leaf support."""
    if _leaf_supports_exclude_prefix(leaf):
        cmd.extend(["--source-prefix", "docs"])
        excludes = (f"docs/{p}" for p in DOC_EXCLUDES)
        _append_flagged(cmd, "--exclude-prefix", excludes)
    else:
        _append_flagged(cmd, "--source-prefix", _doc_prefixes(context.repo))


def _add_hotspot_args(cmd: list[str], context: _LaneContext) -> None:
    """Append hotspot-lane flags: --rev and optional --config."""
    if context.rev is not None:
        cmd.extend(["--rev", context.rev])
    if context.hotspot_config is not None:
        cmd.extend(["--config", str(context.hotspot_config)])


def _append_scope_args(
    cmd: list[str],
    lane: str,
    leaf: Path,
    context: _LaneContext,
) -> None:
    # exec lane: no extra args
    if lane == "exec":
        return

    if lane == "growth":
        _add_growth_args(cmd, context)
        return

    if lane in SOURCE_SCOPED_LANES:
        supports = _leaf_supports_exclude_prefix(leaf)
        cmd.extend(
            _audit_scope_args(
                context.source_prefixes, context.exclude_prefixes, supports
            )
        )
    elif lane == "docs":
        _add_docs_args(cmd, leaf, context)
    elif lane == "hotspot":
        _add_hotspot_args(cmd, context)

    if lane == "security" and context.security_config is not None:
        cmd.extend(["--config", str(context.security_config)])


def _run_lane(
    lane: str,
    leaf: Path,
    context: _LaneContext,
) -> tuple[int, list[dict[str, Any]]]:
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
            cmd, check=False, capture_output=True, text=True,
            timeout=_lane_timeout(),
        ).returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
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

_WaveResult = tuple[
    int,
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]


def _partition_runnable(
    selected: list[str],
    lanes: dict[str, str],
    skills_root: Path,
    context: _LaneContext,
) -> tuple[dict[str, Path], dict[str, dict[str, Any]], int]:
    """Split selected lanes into runnable (leaf exists) vs skipped/error."""
    runnable: dict[str, Path] = {}
    summary: dict[str, dict[str, Any]] = {}
    wave_exit = 0
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
    return runnable, summary, wave_exit


def _collect_lane_results(
    runnable: dict[str, Path],
    context: _LaneContext,
) -> tuple[dict[str, tuple[int, list[dict[str, Any]]]], dict[str, dict[str, Any]]]:
    """Execute runnable lanes in parallel; return results and timings."""
    results: dict[str, tuple[int, list[dict[str, Any]]]] = {}
    timings: dict[str, dict[str, Any]] = {}
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
                "end": datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat(),
                "elapsed": elapsed,
            }
            try:
                exit_code, findings = future.result()
                results[lane] = (exit_code, findings)
            except Exception:
                results[lane] = (2, [])
    return results, timings


def _run_wave(
    selected: list[str],
    lanes: dict[str, str],
    skills_root: Path,
    context: _LaneContext,
) -> _WaveResult:
    """Run selected lanes in parallel, preserving registry order in outputs."""
    runnable, summary, wave_exit = _partition_runnable(
        selected, lanes, skills_root, context
    )
    timings: dict[str, dict[str, Any]] = {}
    wave_findings: list[dict[str, Any]] = []

    if runnable:
        results, timings = _collect_lane_results(runnable, context)

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


def _resolve_accept(
    repo: Path, accept: Path | None, baseline: Path | None
) -> _accept.AcceptPolicy:
    """Auto-discover the in-repo policy, merge --accept and a legacy --baseline."""
    policy = _accept.load_accept(repo, accept)  # raises AcceptError on a bad file
    if baseline is not None:
        rows = _wave_findings.load_baseline(baseline)  # raises on bad input
        policy = policy.merge(_accept.from_baseline(rows))
    return policy


def _apply_accept(
    policy: _accept.AcceptPolicy, findings: list[dict[str, Any]], out_dir: Path
) -> list[dict[str, Any]]:
    """Partition at the report stage; write the accepted + back-compat sidecars."""
    active, accepted, stale = policy.partition(findings, "report")
    (out_dir / "wave_findings.accepted.json").write_text(
        json.dumps({"accepted": accepted, "stale": stale}, indent=2), encoding="utf-8")
    # back-compat: keep the old suppressed.json shape for existing readers
    (out_dir / "wave_findings.suppressed.json").write_text(
        json.dumps({"suppressed": accepted, "stale_baseline": stale}, indent=2),
        encoding="utf-8")
    return active


def _write_wave_outputs(
    out_root: Path,
    wave_exit: int,
    summary: dict[str, dict[str, Any]],
    wave_findings: list[dict[str, Any]],
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


def _missing_required(args: argparse.Namespace) -> list[str]:
    """Wave-run flags absent in normal mode (all optional so --capabilities works)."""
    required = (
        ("--repo", args.repo),
        ("--out-dir", args.out_dir),
        ("--skills-root", args.skills_root),
    )
    return [flag for flag, value in required if value is None]


def _load_registry(args: argparse.Namespace) -> dict[str, str]:
    """Resolve the lane registry: --registry, the committed default, or legacy."""
    if args.registry:
        return load_lanes(args.registry)
    if _DEFAULT_REGISTRY.exists():
        return load_lanes(_DEFAULT_REGISTRY)
    return dict(_LEGACY_LANES)


def _execute(
    args: argparse.Namespace, loaded: dict[str, str], selected: list[str]
) -> int:
    """Run the selected wave, apply the accept policy, and write outputs."""
    args.out_dir.mkdir(parents=True, exist_ok=True)
    context = _LaneContext(
        args.repo,
        args.out_dir,
        args.source_prefix,
        _effective_excludes(args.source_prefix, args.exclude_prefix),
        args.rev,
        args.coverage_json,
        args.security_config,
        args.hotspot_config,
    )
    wave_exit, summary, wave_findings, timings = _run_wave(
        selected, loaded, args.skills_root, context
    )
    policy = _resolve_accept(args.repo, args.accept, args.baseline)
    if policy.entries:
        wave_findings = _apply_accept(policy, wave_findings, args.out_dir)
    return _write_wave_outputs(args.out_dir, wave_exit, summary, wave_findings, timings)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.capabilities:
        print(json.dumps({"version": __version__, "capabilities": CAPABILITIES}))
        return 0
    missing = _missing_required(args)
    if missing:
        print(json.dumps(
            {"status": "error", "error": "missing required args", "missing": missing},
            sort_keys=True,
        ))
        return 2
    loaded = _load_registry(args)
    selected, unknown = _selected_lanes(args.lanes, loaded)
    if unknown:
        print(json.dumps(
            {"status": "error", "error": "Unknown lane(s)", "lanes": unknown},
            sort_keys=True,
        ))
        return 2
    return _execute(args, loaded, selected)


if __name__ == "__main__":
    raise SystemExit(main())
