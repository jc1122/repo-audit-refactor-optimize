#!/usr/bin/env python3
"""Mine per-iteration loop-telemetry KPIs from run artifacts.

R5 discipline: KPIs are MINED from artifacts (git timestamps, ratcheted
baselines, run-dir mtimes, CI run deltas), never reported by the worker.
External waits (CI) are recorded but NEVER trip the regression flag.

Pure functions (``compute_kpi``, ``is_regression``) carry all the contract;
``main()`` is a thin artifact-derivation shell that degrades gracefully when
an artifact is missing and appends one JSON line to the KPI file.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404: trusted git/gh, shell=False
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast


def _repairs(run: dict[str, object]) -> int:
    """Repair count for a worker run, coerced to int (untyped artifact field)."""
    value = run.get("repairs", 0)
    return value if isinstance(value, int) else 0


@dataclass(frozen=True)
class KpiInputs:
    """Already-mined inputs for one KPI record (groups compute_kpi's parameters)."""

    iteration: int
    rows_before: dict[str, int]
    rows_after: dict[str, int]
    phase_seconds: dict[str, float]
    worker_runs: list[dict[str, object]]
    ci_wait_seconds: float


def compute_kpi(inputs: KpiInputs) -> dict[str, object]:
    """Compute the per-iteration KPI record from already-mined inputs.

    rows_closed = total baseline rows removed across repos.
    rows_per_hour = rows_closed normalised by loop-controlled phase time.
    repair_rate = fraction of worker runs that needed a follow-up repair.
    ci_wait_seconds = external wait, recorded passthrough (not loop-controlled).
    """
    iteration = inputs.iteration
    rows_before = inputs.rows_before
    rows_after = inputs.rows_after
    phase_seconds = inputs.phase_seconds
    worker_runs = inputs.worker_runs
    ci_wait_seconds = inputs.ci_wait_seconds
    rows_closed = sum(rows_before.values()) - sum(rows_after.values())
    total_seconds = sum(phase_seconds.values())
    rows_per_hour = rows_closed / (total_seconds / 3600.0) if total_seconds > 0 else 0.0
    repair_rate = (
        sum(1 for run in worker_runs if _repairs(run) > 0) / len(worker_runs)
        if worker_runs
        else 0.0
    )
    return {
        "iteration": iteration,
        "rows_closed": rows_closed,
        "rows_per_hour": rows_per_hour,
        "repair_rate": repair_rate,
        "ci_wait_seconds": ci_wait_seconds,
        "phase_seconds": dict(phase_seconds),
        "total_phase_seconds": total_seconds,
        "worker_count": len(worker_runs),
    }


def _count_baseline_rows(data: object) -> int:
    """Count logical rows in a parsed baseline JSON.

    Handles three shapes:
    - accept.json (``{"version": int, "accept": [...]}``) → len(accept list)
    - legacy flat list (``[...]``) → len(list)
    - legacy multi-key dict (``{"key": [...], ...}``) → sum of list lengths
    """
    if isinstance(data, dict) and "accept" in data:
        val = data["accept"]
        return len(val) if isinstance(val, list) else 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return sum(len(v) for v in data.values() if isinstance(v, list))
    return 0


def build_kpis(
    repo_name: str,
    rows_before_n: int,
    rows_after_n: int,
    worker_runs: list[dict[str, object]],
    phase_seconds: dict[str, float],
    ci_wait_seconds: float,
    iteration: int = 0,
) -> dict[str, object]:
    """Build a full KPI record keyed by explicit repo_name.

    Emits both the per-repo dicts (``rows_before``, ``rows_after``) consumed
    by ``allocate_batches.trailing_yield`` AND the scalar ``rows_closed`` kept
    for back-compat with callers that read only the scalar.
    """
    rows_before = {repo_name: rows_before_n}
    rows_after = {repo_name: rows_after_n}
    inputs = KpiInputs(
        iteration=iteration,
        rows_before=rows_before,
        rows_after=rows_after,
        phase_seconds=phase_seconds,
        worker_runs=worker_runs,
        ci_wait_seconds=ci_wait_seconds,
    )
    record = compute_kpi(inputs)
    # rows_closed and rows_per_hour are overridden below (per-repo scalar + clamp)
    # Augment with per-repo dicts so trailing_yield can read them.
    record["rows_before"] = rows_before
    record["rows_after"] = rows_after
    # Ensure scalar rows_closed = max(before-after, 0) regardless of compute_kpi sign.
    rows_closed = max(rows_before_n - rows_after_n, 0)
    record["rows_closed"] = rows_closed
    # Keep rows_per_hour consistent with the corrected rows_closed scalar.
    total_seconds = cast(float, record["total_phase_seconds"])
    record["rows_per_hour"] = (
        rows_closed / (total_seconds / 3600.0) if total_seconds > 0 else 0.0
    )
    return record


def is_regression(cur: dict[str, object], prev: dict[str, object]) -> bool:
    """True iff a LOOP-CONTROLLED KPI regressed.

    Regression = throughput dropped >20% (rows_per_hour < prev*0.8) OR
    repair burden rose >50% (repair_rate > prev*1.5). External waits
    (ci_wait_seconds and any *_wait_seconds metric) are NEVER considered (R5).
    """
    rph_drop = (
        cast(float, cur["rows_per_hour"]) < cast(float, prev["rows_per_hour"]) * 0.8
    )
    repair_rise = (
        cast(float, cur["repair_rate"]) > cast(float, prev["repair_rate"]) * 1.5
    )
    return bool(rph_drop or repair_rise)


# --------------------------------------------------------------------------
# main(): thin artifact-derivation shell. Each derivation is isolated so a
# missing artifact degrades gracefully and never crashes the loop.
# --------------------------------------------------------------------------


def _git_commit_epoch(repo: Path, sha: str) -> float | None:
    """Committer epoch for a SHA, or None if unavailable."""
    try:
        out = subprocess.run(  # nosec B603 B607: fixed argv, shell=False
            ["git", "-C", str(repo), "show", "-s", "--format=%ct", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def _derive_phase_seconds(
    repo: Path, start_sha: str | None, end_sha: str | None
) -> dict[str, float]:
    """Phase window from git commit timestamps (start SHA -> end SHA)."""
    if not start_sha or not end_sha:
        return {}
    start = _git_commit_epoch(repo, start_sha)
    end = _git_commit_epoch(repo, end_sha)
    if start is None or end is None:
        return {}
    return {"window": max(0.0, end - start)}


def _load_baseline_data(repo: Path, sha: str | None, baseline_rel: str) -> object:
    """Parse raw baseline JSON at a given SHA, or return None on any error."""
    if not sha:
        return None
    try:
        out = subprocess.run(  # nosec B603 B607: fixed argv, shell=False
            ["git", "-C", str(repo), "show", f"{sha}:{baseline_rel}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(out.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def _load_baseline_rows(
    repo: Path, sha: str | None, baseline_rel: str
) -> dict[str, int]:
    """Row counts from a ratcheted baseline JSON at a given SHA.

    Legacy callers receive the original key→count dict. New callers should
    use ``_load_baseline_data`` + ``_count_baseline_rows`` instead.
    """
    data = _load_baseline_data(repo, sha, baseline_rel)
    if data is None:
        return {}
    rows: dict[str, int] = {}
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, list):
                rows[str(key)] = len(val)
            elif isinstance(val, int):
                rows[str(key)] = val
    elif isinstance(data, list):
        rows[Path(baseline_rel).stem] = len(data)
    return rows


def _derive_worker_runs(runs_dir: Path) -> list[dict[str, object]]:
    """One entry per packet run-dir; repairs = follow-up commit count file."""
    runs: list[dict[str, object]] = []
    try:
        subdirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    except OSError:
        return runs
    for sub in subdirs:
        repairs = 0
        repair_file = sub / "repairs.txt"
        try:
            if repair_file.is_file():
                repairs = int(repair_file.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            repairs = 0
        runs.append({"run": sub.name, "repairs": repairs})
    return runs


def _derive_ci_wait_seconds(repo: Path) -> float:
    """CI run created->completed delta via gh; 0.0 if unavailable."""
    try:
        out = subprocess.run(  # nosec B603 B607: fixed argv, shell=False
            [
                "gh",
                "run",
                "list",
                "-L",
                "1",
                "--json",
                "createdAt,updatedAt",
            ],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        )
        runs = json.loads(out.stdout)
        if runs:
            import datetime as _dt

            created = _dt.datetime.fromisoformat(
                runs[0]["createdAt"].replace("Z", "+00:00")
            )
            updated = _dt.datetime.fromisoformat(
                runs[0]["updatedAt"].replace("Z", "+00:00")
            )
            return max(0.0, (updated - created).total_seconds())
    except (
        subprocess.SubprocessError,
        json.JSONDecodeError,
        KeyError,
        ValueError,
        OSError,
    ):
        return 0.0
    return 0.0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mine per-iteration loop-telemetry KPIs from run artifacts."
    )
    parser.add_argument("--iteration", type=int, default=0, help="Iteration number.")
    parser.add_argument(
        "--repo", type=Path, default=Path("."), help="Repo root to mine git from."
    )
    parser.add_argument("--start-sha", default=None, help="Iteration window start SHA.")
    parser.add_argument("--end-sha", default=None, help="Iteration window end SHA.")
    parser.add_argument(
        "--baseline",
        default=".repo-audit/accept.json",
        help="Repo-relative path to the ratcheted baseline / accept JSON.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("/tmp/sp13/runs"),  # nosec B108: override via --runs-dir
        help="Directory holding per-packet worker run-dirs.",
    )
    parser.add_argument(
        "--kpi-file",
        type=Path,
        default=Path("scripts/iteration_kpis.jsonl"),
        help="JSONL file to append one KPI line to.",
    )
    parser.add_argument(
        "--repo-name",
        default=None,
        help=(
            "Logical repo label (e.g. repo-b) used as key in rows_before/rows_after. "
            "Defaults to the resolved name of --repo."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_name: str = args.repo_name or args.repo.resolve().name

    # Each derivation is isolated; a failure yields an empty/zero default.
    try:
        phase_seconds = _derive_phase_seconds(args.repo, args.start_sha, args.end_sha)
    except Exception:
        phase_seconds = {}
    try:
        data_before = _load_baseline_data(args.repo, args.start_sha, args.baseline)
        rows_before_n = (
            _count_baseline_rows(data_before) if data_before is not None else 0
        )
    except Exception:
        rows_before_n = 0
    try:
        data_after = _load_baseline_data(args.repo, args.end_sha, args.baseline)
        rows_after_n = _count_baseline_rows(data_after) if data_after is not None else 0
    except Exception:
        rows_after_n = 0
    try:
        worker_runs = _derive_worker_runs(args.runs_dir)
    except Exception:
        worker_runs = []
    try:
        ci_wait_seconds = _derive_ci_wait_seconds(args.repo)
    except Exception:
        ci_wait_seconds = 0.0

    kpi = build_kpis(
        repo_name=repo_name,
        rows_before_n=rows_before_n,
        rows_after_n=rows_after_n,
        worker_runs=worker_runs,
        phase_seconds=phase_seconds,
        ci_wait_seconds=ci_wait_seconds,
        iteration=args.iteration,
    )

    line = json.dumps(kpi, sort_keys=True)
    try:
        args.kpi_file.parent.mkdir(parents=True, exist_ok=True)
        with args.kpi_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        print(f"failed to append KPI line: {exc}", file=sys.stderr)
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def mine_mprr_kpis(events_path: str, ceiling: int) -> dict[str, float | int]:
    """Mine MPRR loop KPIs from the run-dir event log (R5: derived, never typed)."""
    import json
    from pathlib import Path

    running = 0
    peak = 0
    samples: list[int] = []
    dispatched = merged = conflicts = 0
    for line in Path(events_path).read_text().splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        kind = ev.get("event")
        if kind == "start":
            running += 1
            dispatched += 1
        elif kind in {"merge", "discard"}:
            running = max(0, running - 1)
            if kind == "merge":
                merged += 1
            if ev.get("conflict"):
                conflicts += 1
        peak = max(peak, running)
        samples.append(running)
    mean = sum(samples) / len(samples) if samples else 0.0
    return {
        "dispatched": dispatched,
        "merged": merged,
        "merge_conflict_rate": (conflicts / merged) if merged else 0.0,
        "peak_concurrency": peak,
        "mean_concurrency": round(mean, 3),
        "pool_utilization": round(mean / ceiling, 3) if ceiling else 0.0,
    }
