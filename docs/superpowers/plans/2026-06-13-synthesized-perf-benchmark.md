# Synthesized Performance Benchmark — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a repo has no benchmark surface, let the agent synthesize a focused microbenchmark that the existing `perf-benchmark` engine measures, so `perf-optimization` can verify a real before/after win — preferring deterministic instruction counts over noisy wall-time.

**Architecture:** Three thin, independently-testable subsystems across the existing family. We **do not** rebuild the gate: `perf-benchmark`'s `scoring.py` already fits the Big-O exponent (`_fit_exponent`), gates CV (`_cv`, `--max-cv`), and reads callgrind/cachegrind/perf_stat tiers. We add (A) synthesis primitives in `perf-benchmark-skill`, (B) a static algorithmic-smell leaf in `repo-audit-skills`, (C) orchestration + a new `synthesizable` lane state in `repo-audit-refactor-optimize`. Speed-only; invariant/datatype optimization is out of scope (see spec Future Work).

**Tech Stack:** Python 3.11+ stdlib (cProfile, pstats, argparse, json); `perflint` (via `pylint`) for the smell leaf; the existing `perf-benchmark` pipeline + `perf-optimization` verify-win as the measurement/verdict engines.

**Spec:** `docs/superpowers/specs/2026-06-13-synthesized-perf-benchmark-design.md`

---

## File Structure

**Track A — `perf-benchmark-skill` (repo-P, `/home/jakub/projects/perf-benchmark-skill`)**
- Create: `scripts/profile_discover.py` — cProfile a representative run, emit a ranked hotspot table.
- Create: `scripts/synth_microbench.py` — generate a runnable microbench harness + a `make_input` stub from a target spec.
- Create: `tests/test_profile_discover.py`, `tests/test_synth_microbench.py`.

**Track B — `repo-audit-skills` (repo-A, `/home/jakub/projects/repo-audit-skills`)**
- Create leaf `skills/perf-smell-audit/` mirroring `skills/dead-code-audit/`: `scripts/perf_smell_audit.py`, `scripts/health_common.py` (vendored copy), `SKILL.md`, `pyproject.toml`, `LICENSE`, `tests/{conftest.py,helpers.py,fixtures/{clean,dirty}/pkg/*.py,test_perf_smell_findings.py,test_perf_smell_cli.py}`.

**Track C — `repo-audit-refactor-optimize` (repo-B, this repo)**
- Modify: `scripts/_lane_resolve.py:281` (`_evaluate_performance_lane`) — add the `synthesizable` state.
- Create: `scripts/synthesize_perf.py` — pure gate-decision + report writer over `perf-benchmark` summaries.
- Create: `scripts/graduate_benchmark.py` — copy a proven harness into `benchmarks/` (ledger owned by `perf-benchmark`).
- Create: `tests/test_synthesize_perf.py`, `tests/test_graduate_benchmark.py`, and extend `tests/test_lane_resolve.py` (or create it if absent).

Tracks are independent and may run as three execution sessions. Within a track, do tasks in order.

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

    rows = rank_hotspots(_run_script(args.script), top=args.top)
    args.out.parent.mkdir(parents=True, exist_ok=True)
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_synth_microbench.py -q`
Expected: PASS (2 passed).

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
# perflint message-id prefix; we enable the plugin and disable everything else.
_PERFLINT_PREFIX = "W81"  # perflint warnings live in the W81xx / R81xx range


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
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []


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
    except Exception as exc:  # noqa: BLE001 — leaf must fail soft to EXIT_ERROR
        print(f"perf-smell-audit error: {exc}", file=sys.stderr)
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


def test_extract_inputs_reads_summary_shape():
    summary = {
        "rubric": {
            "dimensions": {
                "Algorithmic Scaling": {"sub_checks": {"complexity_exponent": {"k": 1.9}}},
                "Wall-Time Stability": {"tier": "PASS", "cv": 2.1},
                "CPU Efficiency": {"tier": "PASS"},  # callgrind/perf present
            }
        }
    }
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    assert inp["exponent"] == 1.9
    assert inp["deterministic"] is True
    assert inp["wall_cv_ok"] is True


def test_write_report_renders_verdict(tmp_path):
    out = tmp_path / "perf"
    res = sp.write_report(
        out_dir=out,
        gate={"gate": "refuse", "reason": "degenerate: O(1)", "lane_state": "manual",
              "complexity": "O(1)", "deterministic": True},
        target="find_max",
    )
    assert res.exists()
    assert "honest refusal" in res.read_text().lower()
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


def decide_gate(*, exponent: float, deterministic: bool, wall_cv_ok: bool) -> dict[str, Any]:
    """Decide whether a synthesized benchmark may back a win-claim."""
    complexity = _cl.label(exponent)
    if exponent < _DEGENERATE_EXPONENT:
        return {
            "gate": "refuse",
            "reason": f"degenerate: {complexity} — benchmark does no size-dependent work",
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
    dims = summary.get("rubric", {}).get("dimensions", {})
    algo = dims.get("Algorithmic Scaling", {})
    exponent = algo.get("sub_checks", {}).get("complexity_exponent", {}).get("k", 0.0)
    wall = dims.get("Wall-Time Stability", {})
    cv = wall.get("cv")
    wall_cv_ok = wall.get("tier") not in (None, "N/A", "N/A (noise)") and (
        cv is None or cv <= max_cv
    )
    # deterministic if a callgrind/perf-backed dimension scored (not N/A)
    deterministic = dims.get("CPU Efficiency", {}).get("tier") not in (None, "N/A")
    return {"exponent": float(exponent), "deterministic": bool(deterministic), "wall_cv_ok": bool(wall_cv_ok)}


def write_report(*, out_dir: Path, gate: dict[str, Any], target: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    verdict = "GATE PASS" if gate["gate"] == "pass" else "HONEST REFUSAL (advisory only)"
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

    summary = json.loads(args.summary.read_text())
    inp = extract_gate_inputs(summary, max_cv=args.max_cv)
    gate = decide_gate(**inp)
    write_report(out_dir=args.out_dir, gate=gate, target=args.target)
    print(json.dumps(gate, indent=2))
    return 0 if gate["gate"] == "pass" else 1


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
Expected: PASS (6 passed).

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
- **Type consistency:** `decide_gate(exponent, deterministic, wall_cv_ok)` and `extract_gate_inputs(...)` return keys match across C2/C4; `generate(...)` return dict keys (`bench`, `make_input`, `target_command`, `spec`) match A2 tests; `graduate(...)` returns `{benchmark_dir, copied}` matching C3 tests; `Finding(...)` field order matches `shared/health_common.py`; persisted summary path `rubric.dimensions[...]` is a name-keyed dict per `reporting.py:416`.
- **Open spec questions baked as defaults:** trigger = agent-on-demand; 3-repo split; perf-stat middle tier NOT added (reuse existing tiers). Flagged in spec for veto.
