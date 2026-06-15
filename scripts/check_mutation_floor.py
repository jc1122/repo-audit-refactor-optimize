#!/usr/bin/env python3
"""Tier-1 mutation-kill floor gate for the critical gate modules (#5).

Runs the ``test-effectiveness-audit`` leaf (mutmut==3.6.0) scoped to the
small allowlist of directly unit-tested gate modules in
``scripts/mutation_targets.json`` and fails when any module's mutation
kill rate falls below ``min_kill_rate``.

Unlike the advisory leaf (which emits findings only for modules *below* its
own threshold), this gate measures the kill rate of *every* allowlisted
module by running the leaf with ``min_kill_rate=1.0`` so each module emits a
finding carrying its actual kill rate; an allowlisted module that emits no
finding scored a perfect 1.0. The floor comparison is a pure function
(``floor_violations``) so it is unit-testable without invoking mutmut.

The leaf path comes from ``$LEAF`` (CI clones it) or the local installed
skills dir, mirroring ``scripts/check_coverage_gap.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404: local trusted leaf invocation, shell=False
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "scripts" / "mutation_targets.json"
_LEAF_REL = (
    ".claude/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py"
)
_DEFAULT_LEAF = Path.home() / _LEAF_REL

# Per-def mutant estimate (leaf budget gate) * a generous margin; the
# allowlist is tiny so a high ceiling never blocks the real run.
_MAX_MUTANTS = 5000


def _leaf() -> str:
    return os.environ.get("LEAF") or str(_DEFAULT_LEAF)


def load_targets(path: Path = TARGETS) -> tuple[list[str], float]:
    """Read the allowlisted modules and the kill-rate floor from the manifest."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["modules"]), float(data["min_kill_rate"])


def floor_violations(report: dict[str, float | None], min_kill_rate: float) -> list[str]:
    """Allowlisted modules whose measured kill rate is below the floor.

    A module with an unmeasured (``None``) kill rate is a violation -- the
    gate must fail closed rather than silently pass an unmeasured module.
    The comparison is inclusive: a module exactly at the floor passes.
    """
    violations = []
    for module in report:
        rate = report[module]
        if rate is None or rate < min_kill_rate:
            violations.append(module)
    return sorted(violations)


def _run_leaf(modules: list[str], out_dir: Path) -> list[dict]:
    """Invoke the leaf over *modules* with a 1.0 floor; return raw findings."""
    paths_file = out_dir / "paths.txt"
    paths_file.write_text("\n".join(modules) + "\n", encoding="utf-8")
    config = out_dir / "config.json"
    # min_kill_rate=1.0 forces every measured module to emit a finding that
    # carries its actual kill rate, so we can read all rates (not just the
    # ones below our floor).
    config.write_text(json.dumps({"min_kill_rate": 1.0}), encoding="utf-8")
    leaf_out = out_dir / "leaf"
    cmd = (
        sys.executable, _leaf(),
        "--root", str(ROOT),
        "--out-dir", str(leaf_out),
        "--paths", str(paths_file),
        "--tests-dir", "tests",
        "--max-mutants", str(_MAX_MUTANTS),
        "--config", str(config),
        "--source-prefix", "scripts",
    )
    proc = subprocess.run(  # nosec B603: shell=False, trusted leaf
        cmd, cwd=ROOT, check=False, capture_output=True, text=True
    )
    findings_path = leaf_out / "test-effectiveness_findings.json"
    if not findings_path.exists():
        raise RuntimeError(
            "test-effectiveness leaf produced no findings file; "
            f"exit={proc.returncode} stderr={proc.stderr[-800:]}"
        )
    return json.loads(findings_path.read_text(encoding="utf-8"))


def measure_kill_rates(modules: list[str]) -> dict[str, float | None]:
    """Measure the mutation kill rate of each allowlisted module.

    Modules that emit a finding carry their measured rate in
    ``metric.value``. Allowlisted modules with no finding scored a perfect
    1.0 (nothing below the 1.0 floor we ran with). Returns the rate keyed by
    the allowlist path so unmeasured modules surface as missing keys upstream.
    """
    with tempfile.TemporaryDirectory() as tmp:
        raw = _run_leaf(modules, Path(tmp))
    measured = {f["path"]: f["metric"]["value"] for f in raw}
    report: dict[str, float | None] = {}
    for module in modules:
        report[module] = measured.get(module, 1.0)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tier-1 mutation-kill floor gate for critical gate modules."
    )
    parser.add_argument(
        "--targets", type=Path, default=TARGETS,
        help="Path to mutation_targets.json (modules + min_kill_rate).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    modules, floor = load_targets(args.targets)
    report = measure_kill_rates(modules)
    bad = floor_violations(report, floor)
    if bad:
        violations = [{"module": m, "kill_rate": report[m]} for m in bad]
        print(json.dumps(
            {"status": "fail", "min_kill_rate": floor, "violations": violations},
            indent=2,
        ))
        return 1
    print(json.dumps({
        "status": "pass",
        "min_kill_rate": floor,
        "kill_rates": report,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
