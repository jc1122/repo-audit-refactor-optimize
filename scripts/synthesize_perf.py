# scripts/synthesize_perf.py
"""Gate decision + reporting over a perf-benchmark summary (speed foundation).

Pure logic: given the fitted complexity exponent and tier evidence, decide
whether a synthesized benchmark is gate-quality (may back a win-claim) or must
fall back to an advisory finding (honest refusal). Reuses perf-benchmark's
existing rubric — this module never measures anything itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from scripts import (
    _complexity_label as _cl,
)  # repo-local Big-O label (scripts is a package)

_DEGENERATE_EXPONENT = 0.15  # below this, work is effectively constant ⇒ O(1)


def decide_gate(
    *, exponent: float, deterministic: bool, wall_cv_ok: bool, measured: bool = True
) -> dict[str, Any]:
    """Decide whether a synthesized benchmark may back a win-claim. Three outcomes:

    * ``error``  — no usable scaling evidence (failed/insufficient measurement).
                   NOT a verdict on the code; the *harness* needs fixing. Distinct
                   from refuse.
    * ``refuse`` — measured fine but not gate-quality: degenerate O(1) work, OR
                   wall-time noise with no deterministic tier. Advisory only, no
                   win-claim.
    * ``pass``   — gate-quality; may back a win-claim.
    """
    if not measured:
        return {
            "gate": "error",
            "reason": (
                "no usable scaling evidence (measurement failed or insufficient) "
                "— fix the harness/sizes"
            ),
            "lane_state": "manual",
            "complexity": "unknown",
            "deterministic": deterministic,
        }
    complexity = _cl.label(exponent)
    if exponent < _DEGENERATE_EXPONENT:
        return {
            "gate": "refuse",
            "reason": (
                f"degenerate: {complexity} — benchmark ran but does no "
                "size-dependent work"
            ),
            "lane_state": "manual",
            "complexity": complexity,
            "deterministic": deterministic,
        }
    if not deterministic and not wall_cv_ok:
        return {
            "gate": "refuse",
            "reason": (
                "wall-time noise: CV over bound and no deterministic tier "
                "(callgrind) available"
            ),
            "lane_state": "manual",
            "complexity": complexity,
            "deterministic": deterministic,
        }
    return {
        "gate": "pass",
        "reason": "deterministic instruction count"
        if deterministic
        else "wall-time CV within bound",
        "lane_state": "full",
        "complexity": complexity,
        "deterministic": deterministic,
    }


def extract_gate_inputs(summary: dict[str, Any], *, max_cv: float) -> dict[str, Any]:
    """Read gate inputs, preferring perf-benchmark's stable top-level contract
    (Track A4: ``complexity_exponent`` + ``deterministic_tier``) and falling back
    to rubric internals for older summaries. ``measured`` is False when no scaling
    exponent was produced — that routes to ``error`` (fix the harness), never to a
    false ``degenerate`` verdict."""
    dims = summary.get("rubric", {}).get("dimensions", {})
    algo = dims.get("Algorithmic Scaling", {})

    exponent = summary.get("complexity_exponent")
    if exponent is None:
        exponent = algo.get("sub_checks", {}).get("complexity_exponent", {}).get("k")
    measured = exponent is not None

    deterministic = summary.get("deterministic_tier")
    if deterministic is None:
        deterministic = dims.get("CPU Efficiency", {}).get("tier") not in (None, "N/A")

    wall = dims.get("Wall-Time Stability", {})
    cv = wall.get("cv")
    wall_cv_ok = wall.get("tier") not in (None, "N/A", "N/A (noise)") and (
        cv is None or cv <= max_cv
    )

    return {
        "exponent": float(exponent) if exponent is not None else 0.0,
        "deterministic": bool(deterministic),
        "wall_cv_ok": bool(wall_cv_ok),
        "measured": bool(measured),
    }


def write_report(*, out_dir: Path, gate: dict[str, Any], target: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate.json").write_text(
        json.dumps(gate, indent=2) + "\n", encoding="utf-8"
    )
    verdict = {
        "pass": "GATE PASS",  # nosec B105: gate-outcome label, not a credential
        "refuse": "HONEST REFUSAL (advisory only)",
        "error": "MEASUREMENT ERROR (fix the harness)",
    }.get(gate["gate"], gate["gate"])
    md = (
        f"# Synthesis report — {target}\n\n"
        f"- Verdict: **{verdict}**\n"
        f"- Complexity (empirical): {gate['complexity']}\n"
        f"- Deterministic tier: {gate['deterministic']}\n"
        f"- Lane state: {gate['lane_state']}\n"
        f"- Reason: {gate['reason']}\n"
    )
    report = out_dir / "synthesis_report.md"
    report.write_text(md, encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decide synthesized-benchmark gate from a perf-benchmark summary."
    )
    parser.add_argument(
        "--summary",
        required=True,
        type=Path,
        help="perf-benchmark benchmark_summary.json",
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--max-cv", type=float, default=5.0)
    args = parser.parse_args(argv)

    try:
        summary = json.loads(args.summary.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        gate = {
            "gate": "error",
            "reason": f"unreadable summary: {exc}",
            "lane_state": "manual",
            "complexity": "unknown",
            "deterministic": False,
        }
        write_report(out_dir=args.out_dir, gate=gate, target=args.target)
        print(json.dumps(gate, indent=2))
        return 2
    gate = decide_gate(**extract_gate_inputs(summary, max_cv=args.max_cv))
    write_report(out_dir=args.out_dir, gate=gate, target=args.target)
    print(json.dumps(gate, indent=2))
    return {"pass": 0, "refuse": 1, "error": 2}[cast(str, gate["gate"])]  # nosec B105


def verify_and_decide(*, verdict: dict[str, Any]) -> dict[str, Any]:
    """Turn perf-optimization's verify_win verdict into a synthesis outcome +
    revert directive.

    Never trusts a self-reported win: ``accept`` keeps the change; anything else
    reverts and keeps the evidence (perf-optimization SKILL.md ratchet)."""
    v = verdict.get("verdict")
    if v == "accept":
        return {
            "outcome": "done_win",
            "revert": False,
            "action": "keep change; commit win evidence",
        }
    if v == "reject":
        return {
            "outcome": "done_no_win",
            "revert": True,
            "action": "git revert the change; keep before/after + verdict as evidence",
            "reasons": verdict.get("reasons", []),
        }
    return {
        "outcome": "error",
        "revert": True,
        "action": "verify could not run; revert the unverified change and re-measure",
        "reason": verdict.get("reason", "unknown"),
    }


if __name__ == "__main__":
    sys.exit(main())
