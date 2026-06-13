# Synthesized Performance Benchmark — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a repo has no benchmark surface, let the agent synthesize a focused microbenchmark that the existing `perf-benchmark` engine measures, so `perf-optimization` can verify a real before/after win — preferring deterministic instruction counts over noisy wall-time.

**Architecture:** Three thin, independently-testable subsystems across the existing family. We **do not** rebuild the gate: `perf-benchmark`'s `scoring.py` already fits the Big-O exponent (`_fit_exponent`), gates CV (`_cv`, `--max-cv`), and reads callgrind/cachegrind/perf_stat tiers. We add (A) synthesis primitives in `perf-benchmark-skill`, (B) a static algorithmic-smell leaf in `repo-audit-skills`, (C) orchestration + a new `synthesizable` lane state in `repo-audit-refactor-optimize`. Speed-only; invariant/datatype optimization is out of scope (see spec Future Work).

**Tech Stack:** Python 3.11+ stdlib (cProfile, pstats, argparse, json); `perflint` (via `pylint`) for the smell leaf; the existing `perf-benchmark` pipeline + `perf-optimization` verify-win as the measurement/verdict engines.

**Spec:** `docs/superpowers/specs/2026-06-13-synthesized-perf-benchmark-design.md`

---

## File Structure

**Track A — `perf-benchmark-skill` (repo-P, `/home/jakub/projects/perf-benchmark-skill`)**
- Create: `scripts/profile_discover.py` — cProfile a representative run, emit a ranked hotspot table (A1).
- Create: `scripts/synth_microbench.py` — generate a microbench harness + `make_input` stub, with a `validate_make_input` pre-check (A2).
- Modify: `scripts/perf_benchmark/reporting.py` — `build_summary_contract` exposing `complexity_exponent` + `deterministic_tier` top-level (A4).
- Create/extend: `tests/test_profile_discover.py`, `tests/test_synth_microbench.py`, `tests/test_pipeline_scoring_reporting.py`.

**Track B — `repo-audit-skills` (repo-A, `/home/jakub/projects/repo-audit-skills`)**
- Create leaf `skills/perf-smell-audit/` mirroring `skills/dead-code-audit/`: `scripts/perf_smell_audit.py` (perflint via pylint, `ToolError`→`EXIT_ERROR`), `scripts/health_common.py` (vendored copy), `SKILL.md`, `pyproject.toml`, `LICENSE`, `tests/{conftest.py,helpers.py,fixtures/{clean,dirty}/pkg/*.py,test_perf_smell_findings.py,test_perf_smell_cli.py}`.

**Track C — `repo-audit-refactor-optimize` (repo-B, this repo)**
- Modify: `scripts/_lane_resolve.py:281` (`_evaluate_performance_lane`) — add the `synthesizable` state (C1).
- Create: `scripts/_complexity_label.py` — repo-local Big-O label (C2).
- Create: `scripts/synthesize_perf.py` — gate decision (pass/refuse/**error**) + report + `verify_and_decide` revert directive (C2, C6).
- Create: `scripts/graduate_benchmark.py` — copy a proven harness into `benchmarks/` (ledger owned by `perf-benchmark`) (C3).
- Create: `tests/test_synthesize_perf.py`, `tests/test_graduate_benchmark.py`, `tests/test_synthesis_e2e.py`, `tests/test_synthesis_real_e2e.py`, and `tests/test_lane_resolve.py`.

**Track D — autonomous driver (repo-B)**
- Create: `scripts/synth_run.py` — resumable file-backed state machine (`synth_state.json` + `synth_events.jsonl`) that blocks/resumes at agent-judgment gaps with a `--max-attempts` stop-condition (D1, D2).
- Create: `tests/test_synth_run_state.py`, `tests/test_synth_run_cli.py`.

Tracks A/B are independent; C depends on A4's contract (with a rubric fallback so it can land first); D depends on C. May run as separate execution sessions.

---

# TRACK A — Synthesis primitives (repo-P)

> All Track A commands run from `/home/jakub/projects/perf-benchmark-skill`. Branch first:
> `git checkout -b feat/benchmark-synthesis`

### Task A1: `profile_discover.py` — rank hotspots from a representative run

> **Not redundant with the pipeline's `perf` hotspots:** `perf_benchmark_pipeline.py:505-516`
> already extracts top hotspots from a Linux `perf report`. `profile_discover.py` is the
> **stdlib-only (cProfile) fallback** for the common case where `perf`/valgrind are absent (e.g.
> the current dev box). When `perf` is available, prefer the pipeline's existing `hotspots` output.

**Files:**
- Create: `scripts/profile_discover.py`
- Test: `tests/test_profile_discover.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profile_discover.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import profile_discover as pd  # noqa: E402


def test_rank_hotspots_orders_by_cumulative_time():
    def slow(n):
        return sum(i * i for i in range(n))

    def caller():
        for _ in range(50):
            slow(2000)

    rows = pd.rank_hotspots(caller, top=5)
    # rows are dicts sorted by cumulative time, descending
    assert rows, "expected at least one hotspot row"
    assert rows == sorted(rows, key=lambda r: r["cumulative_s"], reverse=True)
    names = [r["function"] for r in rows]
    assert any("slow" in n for n in names)
    for r in rows:
        assert {"function", "ncalls", "cumulative_s", "total_s"} <= set(r)


def test_main_writes_ranked_json(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text(
        "def work(n):\n    return sorted(range(n), reverse=True)\n\n"
        "def main():\n    [work(1000) for _ in range(20)]\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    out = tmp_path / "ranked.json"
    rc = pd.main(["--script", str(target), "--out", str(out), "--top", "10"])
    assert rc == 0
    data = json.loads(out.read_text())
    assert isinstance(data, list) and data
    assert "work" in {r["function"].split(":")[-1] for r in data} or any(
        "work" in r["function"] for r in data
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_profile_discover.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'profile_discover'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/profile_discover.py
"""Discovery tier: rank function hotspots of a representative run via cProfile.

Deterministic ranking (relative timings only — never used for the win gate).
"""
from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import runpy
import sys
from pathlib import Path
from typing import Any, Callable


def _stats_to_rows(stats: pstats.Stats, top: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # stats.stats: {(file, line, func): (cc, nc, tt, ct, callers)}
    for (fname, lineno, func), (_cc, nc, tt, ct, _callers) in stats.stats.items():
        rows.append(
            {
                "function": f"{Path(fname).name}:{lineno}:{func}",
                "ncalls": nc,
                "total_s": round(tt, 6),
                "cumulative_s": round(ct, 6),
            }
        )
    rows.sort(key=lambda r: (r["cumulative_s"], r["total_s"]), reverse=True)
    return rows[:top]


def rank_hotspots(fn: Callable[[], Any], top: int = 20) -> list[dict[str, Any]]:
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    return _stats_to_rows(pstats.Stats(profiler), top)


def _run_script(path: Path) -> Callable[[], None]:
    def runner() -> None:
        runpy.run_path(str(path), run_name="__main__")

    return runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank hotspots of a representative run.")
    parser.add_argument("--script", required=True, type=Path, help="Python script to run under cProfile")
    parser.add_argument("--out", required=True, type=Path, help="Output ranked JSON path")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        rows = rank_hotspots(_run_script(args.script), top=args.top)
    except BaseException as exc:  # noqa: BLE001 — the representative run is arbitrary user code
        args.out.write_text(json.dumps({"error": f"representative run failed: {exc!r}"}, indent=2) + "\n", encoding="utf-8")
        print(f"profile_discover: representative run failed: {exc!r}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_profile_discover.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/profile_discover.py tests/test_profile_discover.py
git commit -m "feat(synthesis): profile_discover hotspot ranking (cProfile)"
```

### Task A2: `synth_microbench.py` — generate a perf-benchmark-shaped harness

**Files:**
- Create: `scripts/synth_microbench.py`
- Test: `tests/test_synth_microbench.py`

The harness is a CLI that takes `SIZE` as argv[1], builds input via an agent-authored `make_input(size)`, and calls the target. `perf-benchmark` drives it via `--target "python bench_<name>.py {SIZE}"` and does all timing/instrumentation.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synth_microbench.py
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import synth_microbench as sm  # noqa: E402


def test_generate_writes_runnable_harness_and_stub(tmp_path):
    # a target module to benchmark
    pkg = tmp_path / "src"
    pkg.mkdir()
    (pkg / "algo.py").write_text(
        "def find_max(data):\n    return max(data)\n", encoding="utf-8"
    )
    out = tmp_path / "perf" / "find_max"
    paths = sm.generate(
        out_dir=out,
        name="find_max",
        import_root=pkg,
        module="algo",
        func="find_max",
    )
    assert paths["bench"].exists()
    assert paths["make_input"].exists()
    # the stub must be present and raise until the agent fills it
    assert "NotImplementedError" in paths["make_input"].read_text()

    # fill make_input so the harness is runnable, then run it for a size
    paths["make_input"].write_text(
        "def make_input(size):\n    return list(range(size))\n", encoding="utf-8"
    )
    proc = subprocess.run(
        [sys.executable, str(paths["bench"]), "1000"],
        capture_output=True,
        text=True,
        cwd=str(out),
    )
    assert proc.returncode == 0, proc.stderr


def test_target_command_uses_size_placeholder(tmp_path):
    out = tmp_path / "perf" / "x"
    paths = sm.generate(
        out_dir=out, name="x", import_root=tmp_path, module="m", func="f"
    )
    assert "{SIZE}" in paths["target_command"]
    assert paths["bench"].name in paths["target_command"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_synth_microbench.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'synth_microbench'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/synth_microbench.py
"""Synthesize a perf-benchmark-shaped microbench harness for one target.

The harness imports an agent-authored ``make_input(size)`` and the target
callable, then runs the callable once per invocation. perf-benchmark drives it
with ``--target "python bench_<name>.py {SIZE}"`` and owns all timing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_BENCH_TEMPLATE = '''\
"""Synthesized microbench for {func} (target of perf-benchmark). Do not edit by hand."""
import sys
from pathlib import Path

sys.path.insert(0, {import_root!r})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_input import make_input  # agent-authored, same directory
from {module} import {func} as _target


def main() -> None:
    size = int(sys.argv[1])
    data = make_input(size)
    _target(data)


if __name__ == "__main__":
    main()
'''

_MAKE_INPUT_STUB = '''\
"""Agent-authored input generator. Must produce realistic, size-scalable input.

Return whatever single argument ``{func}`` expects, sized by ``size``.
Replace the body below before running the benchmark.
"""


def make_input(size):
    raise NotImplementedError("Author a realistic, scalable input generator for {func}")
'''


def generate(
    *, out_dir: Path, name: str, import_root: Path, module: str, func: str
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bench = out_dir / f"bench_{name}.py"
    make_input = out_dir / "make_input.py"
    bench.write_text(
        _BENCH_TEMPLATE.format(func=func, module=module, import_root=str(import_root)),
        encoding="utf-8",
    )
    make_input.write_text(_MAKE_INPUT_STUB.format(func=func), encoding="utf-8")
    target_command = f'python {bench.name} {{SIZE}}'
    spec = {
        "name": name,
        "module": module,
        "func": func,
        "import_root": str(import_root),
        "bench": str(bench),
        "make_input": str(make_input),
        "target_command": target_command,
    }
    (out_dir / "synth_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    return {"bench": bench, "make_input": make_input, "target_command": target_command, "spec": spec}


def validate_make_input(harness_dir: Path, *, probe_sizes: tuple[int, int] = (256, 1024)) -> dict[str, Any]:
    """Cheap pre-measurement guard run BEFORE the expensive pipeline.

    Catches the common failure modes early instead of paying for a valgrind run that
    then refuses: (1) the stub was never filled (``NotImplementedError``), (2) ``make_input``
    raises, (3) it does not scale (output size does not grow with ``size``). Returns
    ``{"ok": bool, "reason": str, "sizes": {...}}`` — never raises on user-code errors.
    """
    import importlib.util

    path = Path(harness_dir) / "make_input.py"
    if not path.is_file():
        return {"ok": False, "reason": "make_input.py missing"}
    spec = importlib.util.spec_from_file_location("_synth_make_input", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        small, large = probe_sizes
        out_small, out_large = mod.make_input(small), mod.make_input(large)
    except NotImplementedError:
        return {"ok": False, "reason": "make_input is still the stub (NotImplementedError) — author it"}
    except Exception as exc:  # noqa: BLE001 — user code
        return {"ok": False, "reason": f"make_input raised: {exc!r}"}
    try:
        len_small, len_large = len(out_small), len(out_large)
    except TypeError:
        return {"ok": True, "reason": "non-sized input; cannot verify scaling statically", "sizes": None}
    if len_large <= len_small:
        return {"ok": False, "reason": f"make_input does not scale: len {len_small}→{len_large} for size {small}→{large}",
                "sizes": {small: len_small, large: len_large}}
    return {"ok": True, "reason": "scales", "sizes": {small: len_small, large: len_large}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthesize a microbench harness for a target.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--import-root", required=True, type=Path)
    parser.add_argument("--module", required=True)
    parser.add_argument("--func", required=True)
    args = parser.parse_args(argv)
    res = generate(
        out_dir=args.out_dir,
        name=args.name,
        import_root=args.import_root,
        module=args.module,
        func=args.func,
    )
    print(json.dumps(res["spec"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Add validation tests to the same file:

```python
# tests/test_synth_microbench.py  (append)
def test_validate_make_input_flags_unfilled_stub(tmp_path):
    out = tmp_path / "perf" / "x"
    paths = sm.generate(out_dir=out, name="x", import_root=tmp_path, module="m", func="f")
    res = sm.validate_make_input(out)  # stub still raises NotImplementedError
    assert res["ok"] is False and "stub" in res["reason"].lower()


def test_validate_make_input_flags_non_scaling(tmp_path):
    out = tmp_path / "perf" / "x"
    sm.generate(out_dir=out, name="x", import_root=tmp_path, module="m", func="f")
    (out / "make_input.py").write_text("def make_input(size):\n    return [0, 1, 2]\n", encoding="utf-8")
    res = sm.validate_make_input(out)
    assert res["ok"] is False and "scale" in res["reason"].lower()


def test_validate_make_input_accepts_scaling(tmp_path):
    out = tmp_path / "perf" / "x"
    sm.generate(out_dir=out, name="x", import_root=tmp_path, module="m", func="f")
    (out / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n", encoding="utf-8")
    res = sm.validate_make_input(out)
    assert res["ok"] is True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_synth_microbench.py -q`
Expected: PASS (5 passed — 2 generation + 3 validation).

- [ ] **Step 5: Commit**

```bash
git add scripts/synth_microbench.py tests/test_synth_microbench.py
git commit -m "feat(synthesis): synth_microbench harness generator"
```

### Task A3: ~~complexity label in scoring.py~~ — REMOVED (redundant)

**Dropped after code review.** Adding `complexity_label` to `scripts/perf_benchmark/scoring.py`
would be **unused in repo-P** (its only consumer is repo-B's `synthesize_perf`, which carries
its own local `_complexity_label.py` — see Task C2). An unused public function is exactly what
`dead-code-audit` would flag. `scoring.py::_fit_exponent` already returns the exponent `k`; the
persisted summary already exposes it at
`rubric.dimensions["Algorithmic Scaling"].sub_checks.complexity_exponent.k`, which is all the gate
needs. No change to repo-P scoring.

- [ ] **Step 1: Full Track A suite (after A1 + A2)**

Run: `python -m pytest -q`
Expected: PASS (all existing + the 4 new synthesis tests). If any pre-existing test was already
failing on `main`, record it and do not attribute it to this work.

---

# TRACK B — Static algorithmic-smell leaf (repo-A)

> All Track B commands run from `/home/jakub/projects/repo-audit-skills`. Branch first:
> `git checkout -b feat/perf-smell-leaf`
> Reference leaf to mirror exactly: `skills/dead-code-audit/`.
>
> **Scope vs existing leaves (verified):** no repo-A leaf wraps perflint today, and the new leaf
> covers *source-level algorithmic* smells only — it does **not** overlap `exec-audit`, whose PERF
> findings are *execution-level* (serial/duplicate runners, slow tests). Both emit the `PERF`
> signal from the shared schema; they are complementary, not duplicates.

### Task B1: scaffold the leaf (vendored common, pyproject, SKILL stub)

**Files:**
- Create: `skills/perf-smell-audit/scripts/health_common.py` (byte-identical copy of `shared/health_common.py`)
- Create: `skills/perf-smell-audit/pyproject.toml`, `skills/perf-smell-audit/LICENSE`, `skills/perf-smell-audit/SKILL.md`
- Create: `skills/perf-smell-audit/tests/{conftest.py,helpers.py}`

- [ ] **Step 1: Copy the vendored common + license, mirroring dead-code-audit**

```bash
mkdir -p skills/perf-smell-audit/scripts skills/perf-smell-audit/tests/fixtures/clean/pkg skills/perf-smell-audit/tests/fixtures/dirty/pkg
cp shared/health_common.py skills/perf-smell-audit/scripts/health_common.py
cp skills/dead-code-audit/LICENSE skills/perf-smell-audit/LICENSE
cp skills/dead-code-audit/tests/conftest.py skills/perf-smell-audit/tests/conftest.py
cp skills/dead-code-audit/tests/helpers.py skills/perf-smell-audit/tests/helpers.py
```

- [ ] **Step 2: Write `pyproject.toml` pinning perflint + pylint**

```toml
# skills/perf-smell-audit/pyproject.toml
[project]
name = "perf-smell-audit"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pylint>=3.0", "perflint>=0.8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Verify the vendored copy matches the source of truth**

Run: `python3 scripts/check_vendored_common.py` (or the repo's documented equivalent — check `package.json` "scripts" for the exact gate name)
Expected: PASS / no drift for `perf-smell-audit` (the copy is byte-identical).

- [ ] **Step 4: Commit**

```bash
git add skills/perf-smell-audit/scripts/health_common.py skills/perf-smell-audit/pyproject.toml skills/perf-smell-audit/LICENSE skills/perf-smell-audit/tests/conftest.py skills/perf-smell-audit/tests/helpers.py
git commit -m "chore(perf-smell-audit): scaffold leaf (vendored common, pyproject)"
```

### Task B2: fixtures + `analyze_tree` emitting PERF findings

**Files:**
- Create: `skills/perf-smell-audit/tests/fixtures/clean/pkg/clean.py`
- Create: `skills/perf-smell-audit/tests/fixtures/dirty/pkg/dirty.py`
- Create: `skills/perf-smell-audit/scripts/perf_smell_audit.py`
- Test: `skills/perf-smell-audit/tests/test_perf_smell_findings.py`

We assert on **tool + signal**, not exact perflint code numbers (codes vary by perflint version), so the test is robust. The dirty fixture uses a textbook perflint trigger: a loop-invariant computation and list-membership.

- [ ] **Step 1: Write the fixtures**

```python
# tests/fixtures/clean/pkg/clean.py
def total(items):
    allowed = {1, 2, 3}            # set membership — no smell
    return sum(x for x in items if x in allowed)
```

```python
# tests/fixtures/dirty/pkg/dirty.py
def total(items):
    allowed = [1, 2, 3]           # list membership in a loop → perflint smell
    acc = 0
    for x in items:
        n = len(items)            # loop-invariant computation → perflint smell
        if x in allowed:
            acc += x + n
    return acc
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_perf_smell_findings.py
from helpers import FIXTURES, load_module

ps = load_module()


def test_clean_fixture_yields_no_findings():
    findings = ps.analyze_tree(FIXTURES / "clean", source_prefixes=["pkg/"])
    assert findings == []


def test_dirty_fixture_flags_perf_smells():
    findings = ps.analyze_tree(FIXTURES / "dirty", source_prefixes=["pkg/"])
    assert findings, "expected at least one perf smell"
    assert all(f.signal == "PERF" for f in findings)
    assert all(f.evidence_tool == "perflint" for f in findings)
    assert all(f.path.endswith("dirty.py") for f in findings)
    # every finding records the perflint message id as its metric name
    assert all(f.metric_name for f in findings)


def test_missing_tool_raises_tool_error_not_silent_clean(monkeypatch):
    # a missing pylint must be a hard error (EXIT_ERROR), never zero findings
    def _boom(*a, **k):
        raise FileNotFoundError("pylint")

    monkeypatch.setattr(ps.subprocess, "run", _boom)
    import pytest
    with pytest.raises(ps.ToolError):
        ps.analyze_tree(FIXTURES / "dirty", source_prefixes=["pkg/"])


def test_main_returns_exit_error_on_tool_error(monkeypatch, tmp_path):
    def _raise(*a, **k):
        raise ps.ToolError("pylint is not installed")

    monkeypatch.setattr(ps, "analyze_tree", _raise)
    rc = ps.main(["--root", str(FIXTURES / "dirty"), "--source-prefix", "pkg/",
                  "--out-dir", str(tmp_path)])
    assert rc == ps.hc.EXIT_ERROR
```

(`helpers.load_module()` imports the leaf's single `*_audit.py`; confirm the copied `helpers.py` resolves `perf_smell_audit.py` — it locates the lone `scripts/*_audit.py`, so no edit needed.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd skills/perf-smell-audit && python -m pytest tests/test_perf_smell_findings.py -q`
Expected: FAIL — `analyze_tree` undefined.

- [ ] **Step 4: Write the implementation**

```python
# skills/perf-smell-audit/scripts/perf_smell_audit.py
"""Static algorithmic-smell audit: wrap perflint (via pylint) → PERF findings.

Deterministic, advisory, never mutates source. High-precision subset only —
wrong-container, loop-invariant, and related performance anti-patterns.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import health_common as hc

LEAF = "perf-smell"
# pylint message types that mean "pylint could not analyze this file" — never a perf smell.
_TOOL_FAILURE_TYPES = {"fatal", "error"}


class ToolError(RuntimeError):
    """Underlying tool missing or produced unusable output (→ EXIT_ERROR, never silent-clean).

    Mirrors the convention in dead_code_audit.py / quality_audit.py: a missing tool is a
    hard error, not zero findings.
    """


def _python_files(root: Path, source_prefixes: list[str]) -> list[Path]:
    files: list[Path] = []
    for prefix in source_prefixes or [""]:
        base = root / prefix
        if base.is_dir():
            files.extend(sorted(base.rglob("*.py")))
        elif base.suffix == ".py" and base.is_file():
            files.append(base)
    return files


def _run_perflint(files: list[Path], root: Path) -> list[dict]:
    if not files:
        return []
    cmd = [
        sys.executable, "-m", "pylint",
        "--load-plugins=perflint",
        "--disable=all",
        "--enable=perflint",
        "--output-format=json",
        "--score=n",
        *[str(f) for f in files],
    ]
    try:
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    except FileNotFoundError as exc:  # pylint itself absent
        raise ToolError("pylint is not installed") from exc
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        # Non-JSON stdout almost always means the perflint plugin failed to load
        # (pylint prints a usage error to stderr). Treat as a tooling gap, never clean.
        raise ToolError(
            f"pylint/perflint produced unparseable output: {(proc.stderr or '').strip()[:300]}"
        ) from exc


def _rel(path_str: str, root: Path) -> str:
    p = Path(path_str)
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def analyze_tree(root: str | Path, source_prefixes: list[str]) -> list[hc.Finding]:
    root = Path(root)
    files = _python_files(root, source_prefixes)
    findings: list[hc.Finding] = []
    for msg in _run_perflint(files, root):
        if msg.get("type") in _TOOL_FAILURE_TYPES:
            continue  # pylint syntax/import errors in target source are not perf smells
        code = msg.get("message-id", "") or msg.get("symbol", "")
        findings.append(
            hc.Finding(
                leaf=LEAF,
                signal="PERF",
                severity="low",
                path=_rel(msg.get("path", ""), root),
                line_start=int(msg.get("line", 0) or 0),
                line_end=int(msg.get("line", 0) or 0),
                symbol=msg.get("symbol", "") or code,
                metric_name=code,
                metric_value=1.0,
                metric_threshold=0.0,
                evidence_tool="perflint",
                evidence_raw=msg.get("message", "")[:400],
                confidence="medium",
                suggested_action=msg.get("message", "")[:200],
            )
        )
    return hc.sort_findings(findings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Static algorithmic-smell audit (perflint).")
    parser.add_argument("--root", required=True)
    parser.add_argument("--source-prefix", action="append", default=[], dest="source_prefixes")
    parser.add_argument("--out-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        findings = analyze_tree(args.root, args.source_prefixes)
    except ToolError as exc:  # missing/broken tool → EXIT_ERROR, matching sibling leaves
        print(f"perf-smell-audit tool error: {exc}", file=sys.stderr)
        return hc.EXIT_ERROR
    data = hc.write_findings(findings, args.out_dir, LEAF)
    return hc.EXIT_FINDINGS if data else hc.EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd skills/perf-smell-audit && python -m pytest tests/test_perf_smell_findings.py -q`
Expected: PASS (2 passed). If perflint emits zero on the dirty fixture, run `python -m pylint --load-plugins=perflint --disable=all --enable=perflint --output-format=json tests/fixtures/dirty/pkg/dirty.py` to see the live message ids, and adjust the fixture to a pattern perflint flags (keep asserting on tool+signal, not a specific code).

- [ ] **Step 6: Commit**

```bash
git add skills/perf-smell-audit/scripts/perf_smell_audit.py skills/perf-smell-audit/tests/
git commit -m "feat(perf-smell-audit): perflint-backed PERF findings + fixtures"
```

### Task B3: CLI contract test + register the leaf

**Files:**
- Test: `skills/perf-smell-audit/tests/test_perf_smell_cli.py`
- Modify: leaf registry — `package.json` (repo-A installer list) and any `min_version` manifest the family uses. Locate with: `grep -rn "dead-code-audit" package.json bin/ scripts/ | head`.

- [ ] **Step 1: Write the failing CLI test**

```python
# tests/test_perf_smell_cli.py
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "perf_smell_audit.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_cli_clean_exits_zero(tmp_path):
    out = tmp_path / "out"
    rc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(FIXTURES / "clean"),
         "--source-prefix", "pkg/", "--out-dir", str(out)],
    ).returncode
    assert rc == 0
    assert json.loads((out / "perf-smell_findings.json").read_text()) == []


def test_cli_dirty_exits_one_with_findings(tmp_path):
    out = tmp_path / "out"
    rc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(FIXTURES / "dirty"),
         "--source-prefix", "pkg/", "--out-dir", str(out)],
    ).returncode
    assert rc == 1
    data = json.loads((out / "perf-smell_findings.json").read_text())
    assert data and all(d["signal"] == "PERF" for d in data)
```

- [ ] **Step 2: Run to verify it fails, then passes**

Run: `cd skills/perf-smell-audit && python -m pytest tests/test_perf_smell_cli.py -q`
Expected: PASS once Task B2 is in (it exercises the same code via the CLI). If it fails on exit codes, fix `main`'s return path — not the test.

- [ ] **Step 3: Register the leaf**

Mirror the dead-code-audit entry wherever it appears (grep result from Files). Add `perf-smell-audit` with `version: 0.1.0`. Run the repo's release/list gate:
Run: `node bin/install-repo-audit-skills.js --list` (or the documented command)
Expected: `perf-smell-audit` appears in the leaf list.

- [ ] **Step 4: Full Track B gate**

Run: `npm run check` (repo-A's 9-gate chain) — grep the printed gate JSON, never a piped exit code.
Expected: all gates green (vendored-common, lint, tests, etc.).

- [ ] **Step 5: Commit**

```bash
git add skills/perf-smell-audit/tests/test_perf_smell_cli.py package.json
git commit -m "feat(perf-smell-audit): CLI contract tests + leaf registration"
```

---

# TRACK C — Orchestration + lane state (repo-B, this repo)

> All Track C commands run from `/home/jakub/projects/repo-audit-refactor-optimize` on branch `spec/synthesized-perf-benchmark` (already checked out) or a fresh `feat/perf-synthesis-orchestration`.

### Task C1: `synthesizable` lane state

**Files:**
- Modify: `scripts/_lane_resolve.py:281-293` (`_evaluate_performance_lane`)
- Test: `tests/test_lane_resolve.py` (create if absent)

Behavior: no perf surface **and** a runnable test surface **and** `perf-benchmark` usable → `synthesizable` (the agent may synthesize). Without `perf-benchmark` → `manual`. No test surface → `blocked` (unchanged).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lane_resolve.py
import importlib

lr = importlib.import_module("scripts._lane_resolve")

LANE = {"preferred": ["perf-benchmark"], "fallback": ["perf-optimization"], "manual_fallback": "x"}


def _skills(perf_benchmark_usable: bool):
    state = "usable_now" if perf_benchmark_usable else "manual_only"
    return {
        "perf-benchmark": {"state": state},
        "perf-optimization": {"state": "manual_only"},
    }


def test_no_bench_but_test_surface_and_perf_benchmark_is_synthesizable():
    profile = {"has_deterministic_perf_surface": False, "has_deterministic_test_surface": True}
    state, selected, warnings = lr._evaluate_performance_lane(LANE, _skills(True), profile)
    assert state == "synthesizable"
    assert "perf-benchmark" in selected
    assert any("synthesi" in w.lower() for w in warnings)


def test_no_bench_no_perf_benchmark_is_manual():
    profile = {"has_deterministic_perf_surface": False, "has_deterministic_test_surface": True}
    state, _selected, _warnings = lr._evaluate_performance_lane(LANE, _skills(False), profile)
    assert state == "manual"


def test_no_bench_no_test_surface_is_blocked():
    profile = {"has_deterministic_perf_surface": False, "has_deterministic_test_surface": False}
    state, _s, _w = lr._evaluate_performance_lane(LANE, _skills(True), profile)
    assert state == "blocked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lane_resolve.py -q`
Expected: FAIL — first test gets `"manual"`, not `"synthesizable"`.

- [ ] **Step 3: Edit `_evaluate_performance_lane`**

Replace the `if not profile["has_deterministic_perf_surface"]:` block (lines 287-293) with:

```python
    if not profile["has_deterministic_perf_surface"]:
        if profile["has_deterministic_test_surface"]:
            if _all_usable(lane.get("preferred", []), skills):
                warnings.append(
                    "No benchmark surface; agent may synthesize one (perf-benchmark usable)."
                )
                selected = list(lane.get("preferred", []))
                selected.extend(_usable_optionals(lane, skills))
                return "synthesizable", selected, warnings
            warnings.append(
                "No benchmark surface detected; performance work remains manual."
            )
            return "manual", [], warnings
        return "blocked", [], warnings
```

(`_all_usable` and `_usable_optionals` already exist in this module.)

- [ ] **Step 4: Run test to verify it passes + no regressions**

Run: `python -m pytest tests/test_lane_resolve.py tests/ -q`
Expected: PASS (new 3 + existing suite green — currently 101 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/_lane_resolve.py tests/test_lane_resolve.py
git commit -m "feat(lane): add synthesizable performance-lane state"
```

### Task C2: `synthesize_perf.py` — pure gate decision + honest refusal

**Files:**
- Create: `scripts/synthesize_perf.py`
- Test: `tests/test_synthesize_perf.py`

Pure decision logic over a `perf-benchmark` `benchmark_summary.json`. The win-gate passes only when the work is **non-degenerate** (fitted exponent indicates size-dependent work) AND it is measured on a **deterministic tier** (callgrind present) OR the wall-time CV is within bound. Refusal → advisory, no win-claim.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthesize_perf.py
import importlib

sp = importlib.import_module("scripts.synthesize_perf")


def test_decide_gate_pass_on_deterministic_nondegenerate():
    g = sp.decide_gate(exponent=1.0, deterministic=True, wall_cv_ok=False)
    assert g["gate"] == "pass"
    assert g["lane_state"] == "full"


def test_decide_gate_pass_on_wall_time_within_cv():
    g = sp.decide_gate(exponent=2.0, deterministic=False, wall_cv_ok=True)
    assert g["gate"] == "pass"


def test_decide_gate_refuses_degenerate_constant_work():
    g = sp.decide_gate(exponent=0.02, deterministic=True, wall_cv_ok=True)
    assert g["gate"] == "refuse"
    assert "degenerate" in g["reason"].lower()
    assert g["lane_state"] == "manual"


def test_decide_gate_refuses_noisy_nondeterministic():
    g = sp.decide_gate(exponent=1.0, deterministic=False, wall_cv_ok=False)
    assert g["gate"] == "refuse"
    assert "noise" in g["reason"].lower() or "cv" in g["reason"].lower()


def test_decide_gate_errors_when_not_measured():
    # failed/insufficient measurement is an ERROR (fix harness), never a degenerate refuse
    g = sp.decide_gate(exponent=0.0, deterministic=False, wall_cv_ok=False, measured=False)
    assert g["gate"] == "error"
    assert g["lane_state"] == "manual"
    assert "fix the harness" in g["reason"].lower()


def test_extract_inputs_prefers_top_level_contract():
    # Track A4: perf-benchmark exposes a stable top-level contract
    summary = {"complexity_exponent": 1.9, "deterministic_tier": True,
               "rubric": {"dimensions": {"Wall-Time Stability": {"tier": "PASS", "cv": 2.1}}}}
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    assert inp == {"exponent": 1.9, "deterministic": True, "wall_cv_ok": True, "measured": True}


def test_extract_inputs_falls_back_to_rubric_internals():
    summary = {"rubric": {"dimensions": {
        "Algorithmic Scaling": {"sub_checks": {"complexity_exponent": {"k": 1.9}}},
        "Wall-Time Stability": {"tier": "PASS", "cv": 2.1},
        "CPU Efficiency": {"tier": "PASS"},
    }}}
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    assert inp["exponent"] == 1.9 and inp["deterministic"] is True and inp["measured"] is True


def test_extract_inputs_unmeasured_when_no_exponent():
    # pipeline failure → Algorithmic Scaling N/A, no exponent anywhere → measured False
    summary = {"rubric": {"dimensions": {
        "Algorithmic Scaling": {"tier": "N/A", "note": "Insufficient data"},
        "Wall-Time Stability": {"tier": "N/A"},
    }}}
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    assert inp["measured"] is False
    assert sp.decide_gate(**inp)["gate"] == "error"


def test_main_handles_unreadable_summary(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not json", encoding="utf-8")
    rc = sp.main(["--summary", str(bad), "--out-dir", str(tmp_path / "perf"), "--target", "x"])
    assert rc == 2
    assert (tmp_path / "perf" / "synthesis_report.md").exists()


def test_write_report_renders_each_verdict(tmp_path):
    for state, marker in [("pass", "gate pass"), ("refuse", "honest refusal"), ("error", "measurement error")]:
        res = sp.write_report(
            out_dir=tmp_path / state,
            gate={"gate": state, "reason": "r", "lane_state": "manual", "complexity": "O(1)", "deterministic": True},
            target="t",
        )
        assert marker in res.read_text().lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_synthesize_perf.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.synthesize_perf'`.

- [ ] **Step 3: Write the implementation**

```python
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
from typing import Any

from scripts import _complexity_label as _cl  # repo-local Big-O label (scripts is a package)

_DEGENERATE_EXPONENT = 0.15  # below this, work is effectively constant ⇒ O(1)


def decide_gate(*, exponent: float, deterministic: bool, wall_cv_ok: bool, measured: bool = True) -> dict[str, Any]:
    """Decide whether a synthesized benchmark may back a win-claim. Three outcomes:

    * ``error``  — no usable scaling evidence (failed/insufficient measurement). NOT a
                   verdict on the code; the *harness* needs fixing. Distinct from refuse.
    * ``refuse`` — measured fine but not gate-quality: degenerate O(1) work, OR wall-time
                   noise with no deterministic tier. Advisory only, no win-claim.
    * ``pass``   — gate-quality; may back a win-claim.
    """
    if not measured:
        return {
            "gate": "error",
            "reason": "no usable scaling evidence (measurement failed or insufficient) — fix the harness/sizes",
            "lane_state": "manual",
            "complexity": "unknown",
            "deterministic": deterministic,
        }
    complexity = _cl.label(exponent)
    if exponent < _DEGENERATE_EXPONENT:
        return {
            "gate": "refuse",
            "reason": f"degenerate: {complexity} — benchmark ran but does no size-dependent work",
            "lane_state": "manual",
            "complexity": complexity,
            "deterministic": deterministic,
        }
    if not deterministic and not wall_cv_ok:
        return {
            "gate": "refuse",
            "reason": "wall-time noise: CV over bound and no deterministic tier (callgrind) available",
            "lane_state": "manual",
            "complexity": complexity,
            "deterministic": deterministic,
        }
    return {
        "gate": "pass",
        "reason": "deterministic instruction count" if deterministic else "wall-time CV within bound",
        "lane_state": "full",
        "complexity": complexity,
        "deterministic": deterministic,
    }


def extract_gate_inputs(summary: dict[str, Any], *, max_cv: float) -> dict[str, Any]:
    """Read gate inputs, preferring perf-benchmark's stable top-level contract (Track A4:
    ``complexity_exponent`` + ``deterministic_tier``) and falling back to rubric internals
    for older summaries. ``measured`` is False when no scaling exponent was produced — that
    routes to ``error`` (fix the harness), never to a false ``degenerate`` verdict."""
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
    wall_cv_ok = wall.get("tier") not in (None, "N/A", "N/A (noise)") and (cv is None or cv <= max_cv)

    return {
        "exponent": float(exponent) if exponent is not None else 0.0,
        "deterministic": bool(deterministic),
        "wall_cv_ok": bool(wall_cv_ok),
        "measured": bool(measured),
    }


def write_report(*, out_dir: Path, gate: dict[str, Any], target: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    verdict = {
        "pass": "GATE PASS",
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
    parser = argparse.ArgumentParser(description="Decide synthesized-benchmark gate from a perf-benchmark summary.")
    parser.add_argument("--summary", required=True, type=Path, help="perf-benchmark benchmark_summary.json")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--max-cv", type=float, default=5.0)
    args = parser.parse_args(argv)

    try:
        summary = json.loads(args.summary.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        gate = {"gate": "error", "reason": f"unreadable summary: {exc}", "lane_state": "manual",
                "complexity": "unknown", "deterministic": False}
        write_report(out_dir=args.out_dir, gate=gate, target=args.target)
        print(json.dumps(gate, indent=2))
        return 2
    gate = decide_gate(**extract_gate_inputs(summary, max_cv=args.max_cv))
    write_report(out_dir=args.out_dir, gate=gate, target=args.target)
    print(json.dumps(gate, indent=2))
    return {"pass": 0, "refuse": 1, "error": 2}[gate["gate"]]


if __name__ == "__main__":
    sys.exit(main())
```

Also create the tiny label helper so the module has no cross-repo import:

```python
# scripts/_complexity_label.py
"""Local Big-O label from a fitted log-log exponent (repo-B has no cross-repo import to repo-P)."""


def label(k: float) -> str:
    if k < 0.15:
        return "O(1)"
    if k < 0.85:
        return "O(log n)"
    if k < 1.2:
        return "O(n)"
    if k < 1.6:
        return "O(n log n)"
    if k < 2.5:
        return "O(n^2)"
    return "O(n^3+)"
```

(`from scripts import _complexity_label as _cl` works because `scripts/` is a package here — `scripts/__init__.py` exists and tests import via `importlib.import_module("scripts.synthesize_perf")`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_synthesize_perf.py -q`
Expected: PASS (10 passed — 4 gate decisions incl. error, 3 extract variants, unreadable-summary, 2 report renders).

- [ ] **Step 5: Commit**

```bash
git add scripts/synthesize_perf.py scripts/_complexity_label.py tests/test_synthesize_perf.py
git commit -m "feat(perf): synthesize_perf gate decision + honest-refusal report"
```

### Task C3: `graduate_benchmark.py` — persist a proven harness on demand

> **Code-review correction:** graduation **copies the harness only**. It does NOT write the
> ledger. `perf-benchmark` already owns `docs/perf/baseline_ledger.jsonl` via its
> `--baseline-ledger` flag (`perf_benchmark_pipeline.py:796-800` calls
> `perf_benchmark/ledger.py::append_run`, writing the canonical
> `{timestamp_utc, tier, rubric_total, wall_time_mean, dimensions}` entry). Inventing a second
> entry shape here would corrupt that format. After graduation, the agent runs the pipeline
> against the committed harness with `--baseline-ledger docs/perf/baseline_ledger.jsonl`, and the
> existing `append_run` seeds the ledger consistently.

**Files:**
- Create: `scripts/graduate_benchmark.py`
- Test: `tests/test_graduate_benchmark.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graduate_benchmark.py
import importlib

gb = importlib.import_module("scripts.graduate_benchmark")


def test_graduate_copies_harness_into_benchmarks(tmp_path):
    # a synthesized (ephemeral) harness
    src = tmp_path / "run" / "perf" / "find_max"
    src.mkdir(parents=True)
    (src / "bench_find_max.py").write_text("print('bench')\n", encoding="utf-8")
    (src / "make_input.py").write_text("def make_input(n):\n    return list(range(n))\n", encoding="utf-8")

    repo = tmp_path / "repo"
    repo.mkdir()
    res = gb.graduate(harness_dir=src, repo_root=repo, name="find_max")

    assert (repo / "benchmarks" / "find_max" / "bench_find_max.py").exists()
    assert (repo / "benchmarks" / "find_max" / "make_input.py").exists()
    assert res["benchmark_dir"].endswith("benchmarks/find_max")
    assert sorted(res["copied"]) == ["bench_find_max.py", "make_input.py"]


def test_graduate_does_not_write_a_ledger(tmp_path):
    # the ledger is owned by perf-benchmark --baseline-ledger, never by graduation
    src = tmp_path / "h"
    src.mkdir()
    (src / "bench_x.py").write_text("x\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()

    gb.graduate(harness_dir=src, repo_root=repo, name="x")
    assert not (repo / "docs" / "perf" / "baseline_ledger.jsonl").exists()


def test_graduate_is_idempotent(tmp_path):
    src = tmp_path / "h"
    src.mkdir()
    (src / "bench_x.py").write_text("v1\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    gb.graduate(harness_dir=src, repo_root=repo, name="x")
    (src / "bench_x.py").write_text("v2\n", encoding="utf-8")
    gb.graduate(harness_dir=src, repo_root=repo, name="x")  # re-graduate refreshes
    assert (repo / "benchmarks" / "x" / "bench_x.py").read_text() == "v2\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graduate_benchmark.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# scripts/graduate_benchmark.py
"""Graduate a proven synthesized benchmark into the audited repo (on demand).

Copies the harness (*.py) into ``benchmarks/<name>/`` only. The perf trend ledger
is owned entirely by perf-benchmark's ``--baseline-ledger`` (ledger.append_run) — this
script never writes it, so the two never disagree on format.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def graduate(*, harness_dir: Path, repo_root: Path, name: str) -> dict[str, object]:
    harness_dir, repo_root = Path(harness_dir), Path(repo_root)
    dest = repo_root / "benchmarks" / name
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for src in sorted(harness_dir.glob("*.py")):
        shutil.copy2(src, dest / src.name)
        copied.append(src.name)
    return {"benchmark_dir": dest.as_posix(), "copied": copied}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy a synthesized harness into benchmarks/.")
    parser.add_argument("--harness-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    res = graduate(harness_dir=args.harness_dir, repo_root=args.repo_root, name=args.name)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_graduate_benchmark.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/graduate_benchmark.py tests/test_graduate_benchmark.py
git commit -m "feat(perf): graduate_benchmark — copy proven harness (ledger owned by perf-benchmark)"
```

### Task C4: end-to-end synthesis smoke test (ties the pieces together)

**Files:**
- Test: `tests/test_synthesis_e2e.py`

Proves the deterministic decision path end-to-end **without** requiring valgrind: feed a real-shaped `perf-benchmark` summary through `extract_gate_inputs` → `decide_gate` → `write_report`, for both a verified-win shape and a degenerate shape.

- [ ] **Step 1: Write the test**

```python
# tests/test_synthesis_e2e.py
import importlib

sp = importlib.import_module("scripts.synthesize_perf")


def _summary(k, wall_tier, cv, cpu_tier):
    return {"rubric": {"dimensions": {
        "Algorithmic Scaling": {"sub_checks": {"complexity_exponent": {"k": k}}},
        "Wall-Time Stability": {"tier": wall_tier, "cv": cv},
        "CPU Efficiency": {"tier": cpu_tier},
    }}}


def test_e2e_nondegenerate_deterministic_passes(tmp_path):
    summary = _summary(1.95, "PASS", 1.5, "PASS")  # callgrind present
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    gate = sp.decide_gate(**inp)
    report = sp.write_report(out_dir=tmp_path / "perf", gate=gate, target="qsort")
    assert gate["gate"] == "pass" and gate["lane_state"] == "full"
    assert "O(n^2)" in report.read_text()


def test_e2e_degenerate_refuses(tmp_path):
    summary = _summary(0.03, "PASS", 0.4, "N/A")  # constant work, no callgrind
    gate = sp.decide_gate(**sp.extract_gate_inputs(summary, max_cv=5.0))
    sp.write_report(out_dir=tmp_path / "perf", gate=gate, target="const")
    assert gate["gate"] == "refuse" and gate["lane_state"] == "manual"
```

- [ ] **Step 2: Run + full Track C suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (existing 101 + all new Track C tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_synthesis_e2e.py
git commit -m "test(perf): end-to-end synthesis gate smoke test"
```

### Task C5: docs — SKILL.md + pipeline reference + CHANGELOG

**Files:**
- Modify: `SKILL.md` (performance lane: note `synthesizable` + the synthesis flow), `references/pipeline.md` (synthesis stage + artifacts), `references/activation-matrix.md` (performance lane states), `CHANGELOG.md`.

- [ ] **Step 1: Update SKILL.md performance-lane text** — add: "When no benchmark surface exists but a runnable Python surface does and `perf-benchmark` is usable, the lane is `synthesizable`: the agent runs `profile_discover.py`, picks a hotspot, authors `make_input(size)` via `synth_microbench.py`, measures with the `perf-benchmark` pipeline (callgrind tier preferred), gates with `synthesize_perf.py`, and may `graduate_benchmark.py` on demand. Synthesis is agent-triggered, never automatic."

- [ ] **Step 2: Update `references/pipeline.md`** — add the `perf/` artifact layout from the spec and the honest-refusal contract (one paragraph; link the spec).

- [ ] **Step 3: Update `references/activation-matrix.md`** — performance lane states now include `synthesizable`.

- [ ] **Step 4: CHANGELOG.md** — new entry: "feat: synthesized performance benchmark — `synthesizable` lane state, profile-discover/synth-microbench/synthesize-perf/graduate-benchmark, perf-smell leaf (repo-A), reuses perf-benchmark gate."

- [ ] **Step 5: Gate + commit**

Run: `python -m pytest tests/ -q` (docs change is inert) — Expected: PASS.
```bash
git add SKILL.md references/pipeline.md references/activation-matrix.md CHANGELOG.md
git commit -m "docs(perf): document synthesized-benchmark flow + synthesizable lane"
```

---

# TRACK A (cont.) — stable summary contract (repo-P)

### Task A4: expose `complexity_exponent` + `deterministic_tier` at the summary top level

> **Placement fix (code review):** repo-B's gate must not reach into repo-P's nested rubric
> internals (`rubric.dimensions["Algorithmic Scaling"].sub_checks…`). perf-benchmark publishes a
> small stable contract; `synthesize_perf.extract_gate_inputs` already prefers it (Task C2) and
> falls back to the rubric for older summaries.

**Files:**
- Modify: `scripts/perf_benchmark/reporting.py` (where `summary = {"rubric": {...}}` is assembled, ~line 413)
- Test: extend `tests/test_pipeline_scoring_reporting.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_scoring_reporting.py  (append)
from perf_benchmark import reporting


def test_summary_exposes_top_level_contract():
    rubric = {"dimensions": [
        ("Algorithmic Scaling", {"tier": "PASS", "sub_checks": {"complexity_exponent": {"k": 1.93}}}),
        ("CPU Efficiency", {"tier": "PASS"}),  # callgrind/perf backed
    ], "total": 8, "max_possible": 8}
    summary = reporting.build_summary_contract(rubric)
    assert summary["complexity_exponent"] == 1.93
    assert summary["deterministic_tier"] is True


def test_summary_contract_marks_non_deterministic_and_missing_exponent():
    rubric = {"dimensions": [
        ("Algorithmic Scaling", {"tier": "N/A", "note": "Insufficient data"}),
        ("CPU Efficiency", {"tier": "N/A"}),
    ], "total": 0, "max_possible": 0}
    summary = reporting.build_summary_contract(rubric)
    assert summary["complexity_exponent"] is None
    assert summary["deterministic_tier"] is False
```

- [ ] **Step 2: Run to verify it fails** — `python -m pytest tests/test_pipeline_scoring_reporting.py -k contract -q` → FAIL (`build_summary_contract` undefined).

- [ ] **Step 3: Implement** (in `reporting.py`; `rubric["dimensions"]` is the list of `(name, dim)` tuples here, before it is dict-ified into the summary):

```python
def build_summary_contract(rubric: dict) -> dict:
    """Stable top-level signals consumed by repo-B's synthesis gate (decoupled from rubric layout)."""
    dims = dict(rubric.get("dimensions", []))
    algo = dims.get("Algorithmic Scaling", {})
    k = algo.get("sub_checks", {}).get("complexity_exponent", {}).get("k")
    cpu_tier = dims.get("CPU Efficiency", {}).get("tier")
    return {
        "complexity_exponent": k,
        "deterministic_tier": cpu_tier not in (None, "N/A"),
    }
```

Then merge it into the written summary where the `{"rubric": {...}}` dict is built (~line 413):
`summary = {**build_summary_contract(rubric), "rubric": {...}, ...}`.

- [ ] **Step 4: Run + full suite** — `python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/perf_benchmark/reporting.py tests/test_pipeline_scoring_reporting.py
git commit -m "feat(reporting): stable top-level summary contract (complexity_exponent, deterministic_tier)"
```

---

# TRACK C (cont.) — verify→revert seam + real end-to-end

### Task C6: `verify_and_decide` — wire perf-optimization's verdict + the revert instruction

> **Failure-path fix:** the optimize→verify→**revert** path was prose-only. `verify_win.py:226`
> already returns `accept`/`reject` and perf-optimization SKILL.md:94 says "reject means revert +
> keep evidence." This task wires that verdict into the synthesis flow and makes the revert
> instruction explicit and tested. We do **not** reimplement verify_win — we consume its verdict.

**Files:**
- Modify: `scripts/synthesize_perf.py` (add `verify_and_decide`)
- Test: `tests/test_synthesize_perf.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthesize_perf.py  (append)
def test_verify_and_decide_accepts_win():
    res = sp.verify_and_decide(verdict={"verdict": "accept"})
    assert res["outcome"] == "done_win"
    assert res["revert"] is False


def test_verify_and_decide_rejects_and_demands_revert():
    res = sp.verify_and_decide(verdict={"verdict": "reject", "reasons": ["median"]})
    assert res["outcome"] == "done_no_win"
    assert res["revert"] is True
    assert "revert" in res["action"].lower()
    assert res["reasons"] == ["median"]


def test_verify_and_decide_errors_on_verify_error():
    res = sp.verify_and_decide(verdict={"verdict": "error", "reason": "missing summary"})
    assert res["outcome"] == "error"
    assert res["revert"] is True  # safest default: undo the unverified change
```

- [ ] **Step 2: Run to verify it fails** — `python -m pytest tests/test_synthesize_perf.py -k verify_and_decide -q` → FAIL.

- [ ] **Step 3: Implement** (append to `scripts/synthesize_perf.py`):

```python
def verify_and_decide(*, verdict: dict[str, Any]) -> dict[str, Any]:
    """Turn perf-optimization's verify_win verdict into a synthesis outcome + revert directive.

    Never trusts a self-reported win: ``accept`` keeps the change; anything else reverts and
    keeps the evidence (perf-optimization SKILL.md ratchet)."""
    v = verdict.get("verdict")
    if v == "accept":
        return {"outcome": "done_win", "revert": False, "action": "keep change; commit win evidence"}
    if v == "reject":
        return {"outcome": "done_no_win", "revert": True,
                "action": "git revert the change; keep before/after + verdict as evidence",
                "reasons": verdict.get("reasons", [])}
    return {"outcome": "error", "revert": True,
            "action": "verify could not run; revert the unverified change and re-measure",
            "reason": verdict.get("reason", "unknown")}
```

- [ ] **Step 4: Run to verify it passes** — `python -m pytest tests/test_synthesize_perf.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/synthesize_perf.py tests/test_synthesize_perf.py
git commit -m "feat(perf): verify_and_decide — consume verify_win verdict + revert directive"
```

### Task C7: real end-to-end run (no valgrind required)

> **Integration coverage:** C4 fed *crafted* summaries. This runs the **actual** perf-benchmark
> pipeline (wall-time tier) on a **synthesized** harness and feeds its real `benchmark_summary.json`
> through the gate — proving the seam works on every box, valgrind or not.

**Files:**
- Test: `tests/test_synthesis_real_e2e.py`

- [ ] **Step 1: Write the test** (skips cleanly if the pipeline isn't importable/runnable):

```python
# tests/test_synthesis_real_e2e.py
import json, subprocess, sys, importlib
from pathlib import Path
import pytest

sp = importlib.import_module("scripts.synthesize_perf")
PB = Path.home() / "projects" / "perf-benchmark-skill"
PIPELINE = PB / "scripts" / "perf_benchmark_pipeline.py"
SYNTH = PB / "scripts" / "synth_microbench.py"


@pytest.mark.skipif(not PIPELINE.is_file() or not SYNTH.is_file(), reason="perf-benchmark-skill not present")
def test_synthesize_quadratic_target_measures_and_gates(tmp_path):
    # a target with clear O(n^2) behavior
    src = tmp_path / "src"; src.mkdir()
    (src / "algo.py").write_text(
        "def slow_dupes(data):\n"
        "    out = []\n"
        "    for i in range(len(data)):\n"
        "        for j in range(len(data)):\n"
        "            if data[i] == data[j]:\n"
        "                out.append(i)\n"
        "    return out\n", encoding="utf-8")
    perf = tmp_path / "perf" / "slow"
    sys.path.insert(0, str(SYNTH.parent))
    import synth_microbench as sm
    paths = sm.generate(out_dir=perf, name="slow", import_root=src, module="algo", func="slow_dupes")
    (perf / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n", encoding="utf-8")
    assert sm.validate_make_input(perf)["ok"] is True

    out = tmp_path / "pbout"
    rc = subprocess.run(
        [sys.executable, str(PIPELINE), "--root", str(perf), "--out-dir", str(out),
         "--target", paths["target_command"], "--sizes", "200,400,800,1600",
         "--tier", "fast", "--expected-complexity", "quadratic"],
        capture_output=True, text=True, cwd=str(perf),
    ).returncode
    summary_path = out / "benchmark_summary.json"
    if not summary_path.is_file():
        pytest.skip("pipeline did not produce a summary in this environment")

    gate = sp.decide_gate(**sp.extract_gate_inputs(json.loads(summary_path.read_text()), max_cv=15.0))
    # on a noisy CI box CV may exceed bound → refuse is acceptable; degenerate/error is NOT
    assert gate["gate"] in {"pass", "refuse"}
    assert gate["complexity"] in {"O(n^2)", "O(n log n)", "O(n)", "O(n^3+)"}  # measured, not O(1)
```

- [ ] **Step 2: Run** — `python -m pytest tests/test_synthesis_real_e2e.py -q` → PASS or SKIP (never degenerate/error on a real quadratic target). Record which (pass vs skip) in the run report.

- [ ] **Step 3: Commit**

```bash
git add tests/test_synthesis_real_e2e.py
git commit -m "test(perf): real end-to-end synthesize → pipeline → gate (wall-time tier)"
```

---

# TRACK D — Autonomous driver (repo-B)

> A file-backed state machine that sequences the pipeline unattended, **blocking** at the two
> (now three, counting "apply the change") irreducible agent-judgment gaps with an explicit status,
> and **resuming** when the agent supplies the input and re-invokes the matching subcommand —
> the same "no state in chat, re-invoke" model as MPRR (`mprr_run.py` + `mprr_state.json`).

### Task D1: state core — load / transition / status (resumable, file-backed)

**Files:**
- Create: `scripts/synth_run.py`
- Test: `tests/test_synth_run_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synth_run_state.py
import importlib
import pytest

sr = importlib.import_module("scripts.synth_run")


def test_initial_state_is_init(tmp_path):
    assert sr.load_state(tmp_path)["state"] == "init"


def test_legal_transition_persists_and_logs(tmp_path):
    sr.transition(tmp_path, "awaiting_hotspot", candidates=[{"id": "h1"}])
    st = sr.load_state(tmp_path)
    assert st["state"] == "awaiting_hotspot"
    assert st["data"]["candidates"] == [{"id": "h1"}]
    events = (tmp_path / "synth_events.jsonl").read_text().splitlines()
    assert events and '"to": "awaiting_hotspot"' in events[-1]


def test_illegal_transition_raises(tmp_path):
    with pytest.raises(ValueError):
        sr.transition(tmp_path, "done_win")  # from init, not allowed


def test_state_is_resumable_across_processes(tmp_path):
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.transition(tmp_path, "awaiting_make_input", target="find_max")
    # a fresh "process" only reads the file
    st = sr.load_state(tmp_path)
    assert st["state"] == "awaiting_make_input" and st["data"]["target"] == "find_max"


def test_terminal_states_have_no_outgoing(tmp_path):
    assert sr._TRANSITIONS["gated_refuse"] == set()
    assert sr._TRANSITIONS["done_win"] == set()
```

- [ ] **Step 2: Run to verify it fails** — `python -m pytest tests/test_synth_run_state.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement the state core**

```python
# scripts/synth_run.py
"""Autonomous synthesis driver: a resumable, file-backed state machine.

Sequences discover → select → measure → gate → (optimize) → verify. At each irreducible
agent-judgment gap it BLOCKS in an ``awaiting_*`` state with the info the agent needs, then
resumes when the agent re-invokes the matching subcommand with its input. State lives in
``synth_state.json`` + ``synth_events.jsonl`` under --run-dir — never in chat (the MPRR model).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# from -> allowed {to}.  awaiting_* are the BLOCKED states; gated_refuse/done_* are terminal.
_TRANSITIONS: dict[str, set[str]] = {
    "init": {"awaiting_hotspot"},
    "awaiting_hotspot": {"awaiting_make_input"},
    "awaiting_make_input": {"awaiting_make_input", "gated_pass", "gated_refuse", "gated_error"},
    "gated_error": {"awaiting_make_input", "done_no_win"},   # fix harness & retry, or give up
    "gated_refuse": set(),                                   # terminal: advisory only
    "gated_pass": {"awaiting_optimization"},
    "awaiting_optimization": {"done_win", "done_no_win"},
    "done_win": set(),
    "done_no_win": set(),
}
_BLOCKED = {"awaiting_hotspot", "awaiting_make_input", "awaiting_optimization"}


def _state_path(run_dir: Path) -> Path:
    return Path(run_dir) / "synth_state.json"


def load_state(run_dir: str | Path) -> dict[str, Any]:
    p = _state_path(run_dir)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"state": "init", "data": {}}


def _append_event(run_dir: Path, event: dict[str, Any]) -> None:
    with (Path(run_dir) / "synth_events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def transition(run_dir: str | Path, to: str, **data: Any) -> dict[str, Any]:
    run_dir = Path(run_dir)
    st = load_state(run_dir)
    frm = st["state"]
    if to not in _TRANSITIONS.get(frm, set()):
        raise ValueError(f"illegal transition {frm} -> {to}")
    st["state"] = to
    st["data"].update(data)
    run_dir.mkdir(parents=True, exist_ok=True)
    _state_path(run_dir).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    _append_event(run_dir, {"from": frm, "to": to, **data})
    return st


def status(run_dir: str | Path) -> dict[str, Any]:
    st = load_state(run_dir)
    return {"state": st["state"], "blocked": st["state"] in _BLOCKED, "data": st["data"]}
```

- [ ] **Step 4: Run to verify it passes** — `python -m pytest tests/test_synth_run_state.py -q` → PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/synth_run.py tests/test_synth_run_state.py
git commit -m "feat(driver): synth_run state core — resumable file-backed state machine"
```

### Task D2: subcommands — blocked/resume at agent gaps + stop-condition

**Files:**
- Modify: `scripts/synth_run.py` (add the CLI + transition drivers)
- Test: `tests/test_synth_run_cli.py`

Each subcommand runs deterministic work, then either advances or **blocks**. Expensive external
calls (real profiling, the perf-benchmark pipeline) are injectable so the flow is unit-testable
without valgrind: `measure` accepts `--summary` (a pre-produced `benchmark_summary.json`) and runs
the cheap `validate_make_input` guard first.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synth_run_cli.py
import importlib, json
from pathlib import Path

sr = importlib.import_module("scripts.synth_run")
sm = importlib.import_module("scripts.synthesize_perf")  # reused by measure


def _summary(k, cpu_tier="PASS", wall_tier="PASS", cv=1.0):
    return {"complexity_exponent": k, "deterministic_tier": cpu_tier != "N/A",
            "rubric": {"dimensions": {"Wall-Time Stability": {"tier": wall_tier, "cv": cv},
                                      "CPU Efficiency": {"tier": cpu_tier}}}}


def test_select_blocks_awaiting_make_input(tmp_path):
    sr.transition(tmp_path, "awaiting_hotspot", candidates=[{"id": "h1", "function": "algo.py:1:f"}])
    rc = sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
                  "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    assert rc == 0
    assert sr.status(tmp_path)["state"] == "awaiting_make_input"
    assert sr.status(tmp_path)["blocked"] is True


def test_measure_blocks_when_make_input_unfilled(tmp_path):
    # synthesize first so the stub exists
    (tmp_path / "src").mkdir()
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
             "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    s = _summary(1.9)
    sp_path = tmp_path / "s.json"; sp_path.write_text(json.dumps(s))
    rc = sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(sp_path)])
    # the cheap guard fires: stub still raises NotImplementedError → stays blocked, NOT measured
    assert rc != 0
    assert sr.status(tmp_path)["state"] == "awaiting_make_input"
    assert "make_input" in json.dumps(sr.status(tmp_path)["data"]).lower()


def test_measure_passes_gate_when_inputs_ready(tmp_path):
    (tmp_path / "src").mkdir()
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
             "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    harness = Path(sr.load_state(tmp_path)["data"]["harness_dir"])
    (harness / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n")
    sp_path = tmp_path / "s.json"; sp_path.write_text(json.dumps(_summary(1.9)))
    rc = sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(sp_path)])
    assert rc == 0
    assert sr.status(tmp_path)["state"] == "gated_pass"


def test_measure_error_increments_attempts_and_stops_after_max(tmp_path):
    (tmp_path / "src").mkdir()
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
             "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    harness = Path(sr.load_state(tmp_path)["data"]["harness_dir"])
    (harness / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n")
    err = tmp_path / "err.json"
    err.write_text(json.dumps({"rubric": {"dimensions": {"Algorithmic Scaling": {"tier": "N/A"}}}}))
    # first error → back to awaiting_make_input; with --max-attempts 1 the second gives up
    sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(err), "--max-attempts", "1"])
    assert sr.status(tmp_path)["state"] == "awaiting_make_input"
    (harness / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n")
    sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(err), "--max-attempts", "1"])
    assert sr.status(tmp_path)["state"] == "done_no_win"  # stop-condition hit
```

- [ ] **Step 2: Run to verify it fails** — `python -m pytest tests/test_synth_run_cli.py -q` → FAIL.

- [ ] **Step 3: Implement the subcommands** (append to `scripts/synth_run.py`):

```python
# scripts/synth_run.py  (append)
from scripts import synthesize_perf as _gate

# synth_microbench lives in perf-benchmark-skill; import by path so the driver stays repo-local.
def _load_synth_microbench():
    import importlib.util, os
    root = os.environ.get("PERF_BENCHMARK_ROOT", str(Path.home() / "projects" / "perf-benchmark-skill"))
    spec = importlib.util.spec_from_file_location("synth_microbench", Path(root) / "scripts" / "synth_microbench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _cmd_select(a: argparse.Namespace) -> int:
    sm = _load_synth_microbench()
    perf_dir = Path(a.run_dir) / "perf" / a.name
    res = sm.generate(out_dir=perf_dir, name=a.name, import_root=Path(a.import_root),
                      module=a.module, func=a.func)
    transition(a.run_dir, "awaiting_make_input", hotspot=a.hotspot, target=a.name,
               harness_dir=str(perf_dir), make_input=str(res["make_input"]),
               target_command=res["target_command"],
               note=f"Author make_input(size) at {res['make_input']}, then run `measure`.")
    return 0


def _cmd_measure(a: argparse.Namespace) -> int:
    sm = _load_synth_microbench()
    st = load_state(a.run_dir)
    harness = Path(st["data"]["harness_dir"])
    guard = sm.validate_make_input(harness)
    if not guard["ok"]:
        # stay blocked at awaiting_make_input with the reason — never advance on a bad harness
        transition(a.run_dir, "awaiting_make_input", make_input_check=guard,
                   note=f"make_input not ready: {guard['reason']}")
        print(json.dumps(guard, indent=2))
        return 1
    summary = json.loads(Path(a.summary).read_text())
    gate = _gate.decide_gate(**_gate.extract_gate_inputs(summary, max_cv=a.max_cv))
    _gate.write_report(out_dir=harness, gate=gate, target=st["data"]["target"])
    if gate["gate"] == "pass":
        transition(a.run_dir, "gated_pass", gate=gate)
        return 0
    if gate["gate"] == "refuse":
        transition(a.run_dir, "gated_refuse", gate=gate)  # terminal advisory
        return 1
    # gate == "error": bump attempts, retry or stop
    attempts = int(st["data"].get("attempts", 0)) + 1
    transition(a.run_dir, "gated_error", gate=gate, attempts=attempts)
    if attempts > a.max_attempts:  # allow up to --max-attempts retries, then give up
        transition(a.run_dir, "done_no_win", reason=f"gave up after {attempts} failed measurements")
    else:
        transition(a.run_dir, "awaiting_make_input", note="measurement error; fix the harness and retry")
    return 2


def _cmd_status(a: argparse.Namespace) -> int:
    print(json.dumps(status(a.run_dir), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Autonomous synthesis driver.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("select"); s.set_defaults(fn=_cmd_select)
    s.add_argument("--run-dir", required=True)
    s.add_argument("--hotspot", required=True)
    s.add_argument("--import-root", required=True)
    s.add_argument("--module", required=True)
    s.add_argument("--func", required=True)
    s.add_argument("--name", required=True)

    m = sub.add_parser("measure"); m.set_defaults(fn=_cmd_measure)
    m.add_argument("--run-dir", required=True)
    m.add_argument("--summary", required=True, help="benchmark_summary.json from the pipeline")
    m.add_argument("--max-cv", type=float, default=5.0)
    m.add_argument("--max-attempts", type=int, default=3)

    st = sub.add_parser("status"); st.set_defaults(fn=_cmd_status)
    st.add_argument("--run-dir", required=True)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify it passes** — `python -m pytest tests/test_synth_run_cli.py -q` → PASS (4 passed).

- [ ] **Step 5: Full Track C+D suite** — `python -m pytest tests/ -q` → PASS (101 existing + all new). Record the count.

- [ ] **Step 6: Commit**

```bash
git add scripts/synth_run.py tests/test_synth_run_cli.py
git commit -m "feat(driver): synth_run subcommands — blocked/resume gaps + stop-condition"
```

> **Out of scope for D (documented limits):** the `discover` subcommand (wrapping `profile_discover`
> + `perf-smell`) and the `verify` subcommand (wrapping a real second pipeline run + `verify_win` +
> `verify_and_decide`) follow the identical inject-and-transition pattern; they are deferred to a
> D3 follow-up to keep this plan's first cut bounded. The state machine already declares their
> transitions (`awaiting_optimization → done_win|done_no_win`), so adding them is additive.

---

## Cross-track integration note

The agent-facing loop (documented in SKILL.md, not a script) is:
`profile_discover` (or the pipeline's own `perf` hotspots when `perf` is available) **+** `perf-smell-audit` findings → agent picks a hotspot → `synth_microbench.generate` → agent fills `make_input` → `perf_benchmark_pipeline --target "<target_command>" --sizes … --expected-complexity … --tier <callgrind when present>` → `synthesize_perf --summary benchmark_summary.json` (gate) → on pass, `select_candidate` + apply one change + re-run pipeline + `verify_win` → optional `graduate_benchmark` (copies the harness only). Every step writes into the run's `perf/` dir; only graduation writes into the audited repo. **Ledger:** to seed a perf trend after graduation, the agent runs the pipeline against the committed harness with `--baseline-ledger docs/perf/baseline_ledger.jsonl` — the existing `perf_benchmark/ledger.py::append_run` owns that file; nothing in this plan writes it directly.

---

## Self-Review (completed by planner)

- **Spec coverage:** discovery (A1 + Track B smell leaf) ✓; synthesize microbench (A2) ✓; deterministic gate / Big-O fit — **reused from existing `scoring.py`** (`_fit_exponent`, `_cv`, `--max-cv`, callgrind/cachegrind/perf_stat tiers), not rebuilt ✓; honest refusal (C2) ✓; `synthesizable` lane (C1) ✓; ephemeral artifacts + graduate-on-demand (C3) ✓; agent-on-demand trigger (C1 message + C5 docs) ✓; 3-repo split ✓; invariant/datatype → Future Work, no task ✓ (intentional).
- **Redundancy review (vs existing code):**
  - **A3 dropped** — adding `complexity_label` to repo-P `scoring.py` would be unused there (dead-code risk); only repo-B's `synthesize_perf` needs it, via its own `_complexity_label.py`.
  - **C3 ledger removed** — `perf_benchmark_pipeline.py:796-800` already owns `baseline_ledger.jsonl` via `ledger.append_run`; graduation copies the harness only and the existing `--baseline-ledger` seeds the ledger.
  - **gate reuse** — `decide_gate`/`extract_gate_inputs` are a thin policy *over* the existing rubric tiers (Wall-Time Stability `N/A (noise)`, Algorithmic Scaling exponent), not a re-implementation of CV/fit math.
  - **`profile_discover`** — stdlib (cProfile) discovery is the fallback to the pipeline's existing `perf`-based `hotspots` (line 505-516); used only where `perf` is absent. Not a duplicate path.
  - **`perf-smell` scope** — source-level algorithmic smells (perflint); no overlap with `exec-audit`'s execution-level PERF findings (slow tests, serial runners). No existing repo-A leaf wraps perflint.
- **Placeholder scan:** no TBD/TODO; every code step shows full code; perflint exact codes deliberately not hard-coded (tests assert tool+signal) with a live-discovery fallback step (B2 Step 5).
- **Type consistency:** `decide_gate(exponent, deterministic, wall_cv_ok, measured=True)` and `extract_gate_inputs(...)` return keys (`exponent, deterministic, wall_cv_ok, measured`) match across C2/C4/D2; `generate(...)` return dict keys (`bench`, `make_input`, `target_command`, `spec`) match A2 tests; `validate_make_input(...)` returns `{ok, reason, …}` consumed by D2; `graduate(...)` returns `{benchmark_dir, copied}` matching C3 tests; `verify_and_decide(...)` returns `{outcome, revert, action, …}`; `synth_run` transitions match `_TRANSITIONS` keys; `Finding(...)` field order matches `shared/health_common.py`; top-level summary contract (`complexity_exponent`, `deterministic_tier`) produced by A4 and read by C2.
- **Revision 2 — robustness + autonomy (this pass, per code review):**
  - **Failure-vs-degenerate split (C2):** a failed/insufficient measurement now returns `gate="error"` ("fix the harness", manual), never a false `degenerate` refuse; confirmed the pipeline emits `{"error":…}` per tier (`pipeline.py:186/216/290/329`) → Algorithmic Scaling `N/A`. Unreadable summary → `error`, exit 2.
  - **Tool-absence (B2):** perf-smell now raises `ToolError → EXIT_ERROR` on missing `pylint`/`perflint` (matching `dead_code_audit.py:92` / `quality_audit.py:127`), never silent-clean; skips pylint syntax/import (`fatal`/`error`) messages so they aren't mis-emitted as PERF.
  - **Crash handling:** `profile_discover` wraps the arbitrary representative run (writes `{"error":…}`, exit 2); `synthesize_perf.main` wraps summary load.
  - **`make_input` pre-validation (A2):** cheap `validate_make_input` (stub-filled? scales?) runs **before** the expensive pipeline; the driver blocks on failure instead of paying for a refused valgrind run.
  - **Placement (A4):** repo-B no longer reaches into repo-P rubric internals — perf-benchmark exposes a stable top-level contract; the gate prefers it, rubric read is a fallback.
  - **Verify→revert seam (C6):** the critical "optimization made it worse" path is now wired and tested — consumes `verify_win`'s `accept`/`reject`, emits an explicit revert directive (never trusts a self-reported win).
  - **Real e2e (C7):** an actual pipeline run (wall-time tier, no valgrind) on a synthesized quadratic target → gate; skips cleanly where the pipeline can't run.
  - **Autonomous driver (Track D):** `synth_run.py` is a resumable, file-backed state machine (`synth_state.json` + `synth_events.jsonl`, MPRR model) that blocks at the agent-judgment gaps (`awaiting_hotspot/make_input/optimization`) and carries a `--max-attempts` stop-condition. D's `discover`/`verify` subcommands are explicitly deferred to D3 (transitions already declared).
- **Open spec questions baked as defaults:** trigger = agent-on-demand; 3-repo split; perf-stat middle tier NOT added (reuse existing tiers). Flagged in spec for veto.
