# mine_iteration_kpis.py Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `scripts/mine_iteration_kpis.py` to full self-audit cleanliness — characterize it with behavior tests (coverage 38.4% → >50%), then remediate the 9 wave findings it carries — taking the repo-B convergence gate from **20 → 11**.

**Architecture:** Two phases under the skill's own remediation playbook. **Phase 1 (TEST signal)** adds characterization tests so the coverage-gate stops freezing the file — this is the mandatory "characterize-first" step and must land before any remediation. **Phase 2** then resolves the now-unfrozen findings as three single-signal-class commits (SECURITY → TYPE → COMPLEXITY). **Phase 3** ships a patch release mirroring the v0.7.1 flow.

**Tech Stack:** Python 3.14, pytest + pytest-cov + coverage 7.x, mypy 2.1.0, bandit 1.9.4, lizard, ruff; deterministic leaves from `repo-audit-skills`.

---

## Background (read once)

The dogfood gate (`scripts/check_wave_baseline.py`, scoped to `scripts/`, equality-ratcheted vs `scripts/wave_baseline.json`) currently fails with **20 findings**. Nine of them sit on this one file, and the coverage lane freezes all nine because the file is at **38.4%** line coverage (the `coverage-gap-audit` threshold is `min_file_coverage = 50.0`, so a file ≤ 50% is a `TEST` finding and every finding in it is demoted to *characterize-first* — see `references/prioritization.md`). So no remediation is permitted until coverage clears 50%.

The 9 findings on `scripts/mine_iteration_kpis.py`:

| Signal | Detail | Source line(s) |
|---|---|---|
| SECURITY `bandit_B404` | `import subprocess` | 17 |
| SECURITY `bandit_B603`/`B607` | 3× `subprocess.run` (git/gh, fixed argv) | 79, 110, 153 |
| SECURITY `bandit_B108` | hardcoded `/tmp/sp13/runs` default | 208 |
| TYPE `misc@41` + `operator@41` | `object` arithmetic in `repair_rate` | 41 |
| TYPE `operator@65`, `operator@66` | `object` arithmetic in `is_regression` | 65, 66 |
| COMPLEXITY `parameter_count` | `compute_kpi` has 6 params (> `max_params=5`) | 22 |

Confirmed facts the plan relies on: mypy reports exactly 6 errors on these lines (→ 4 de-duped identities); bandit reports B404@17, B603+B607@{79,110,153}, B108@208; `compute_kpi`/`is_regression` have **no callers** outside this module and its test (a signature change is safe); the repo's suppression convention is inline `# nosec Bxxx: reason` (see `scripts/run_diagnosis_wave.py:9,117`).

**Important:** Phase 1 (tests) does **not** change the gate count — the 9 findings still appear in the `scripts/`-scoped wave; tests only flip them from *frozen* to *executable*. The gate drops to 11 only after Phase 2.

---

## File Structure

- **Modify** `tests/test_mine_iteration_kpis.py` — extend (never overwrite) with a temp-git-repo helper and characterization tests for `main()` and every derivation helper.
- **Modify** `scripts/mine_iteration_kpis.py` — Phase 2 only: inline `# nosec`, `from typing import cast` + a `_repairs` helper + casts, and a `KpiInputs` dataclass.
- **Modify** `SKILL.md`, `CHANGELOG.md` — Phase 3 version bump.

---

## Phase 0 — Setup

### Task 0: Create the working branch and commit the plan

> The repo is currently on `main` (post-v0.7.1 merge). All Phase 1–2 commits must land on a feature branch; Phase 3 merges it back. Do this first or every commit below pollutes `main`.

- [ ] **Step 1: Branch (prefer the worktree skill if available)**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
git checkout -b feat/kpis-convergence
```
(Or use `superpowers:using-git-worktrees` for an isolated worktree — then run all tasks there.)

- [ ] **Step 2: Commit this plan onto the branch**

```bash
git add docs/superpowers/plans/2026-06-14-mine-iteration-kpis-convergence.md
git commit -m "docs(plan): mine_iteration_kpis convergence plan"
```

---

## Phase 1 — Characterization (TEST signal)

### Task 1: Temp-repo helper + `main()` happy path

**Files:**
- Test: `tests/test_mine_iteration_kpis.py` (append)

- [ ] **Step 1: Add imports + a temp-git-repo helper at the top of the test file (below the existing imports)**

```python
from pathlib import Path


def _init_repo(path):
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)


def _commit(repo, relpath, content):
    f = repo / relpath
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", relpath], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True)
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
```

- [ ] **Step 2: Write the failing `main()` happy-path test**

```python
def test_main_appends_line_prints_and_returns_zero(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    start = _commit(repo, "scripts/wave_baseline.json",
                    json.dumps([{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]))
    end = _commit(repo, "scripts/wave_baseline.json", json.dumps([{"id": 1}]))
    runs = tmp_path / "runs"
    (runs / "p1").mkdir(parents=True)
    (runs / "p2").mkdir()
    (runs / "p1" / "repairs.txt").write_text("1", encoding="utf-8")
    monkeypatch.setattr(m, "_derive_ci_wait_seconds", lambda repo: 0.0)
    kpi_file = tmp_path / "out" / "kpis.jsonl"

    rc = m.main([
        "--iteration", "7", "--repo", str(repo),
        "--start-sha", start, "--end-sha", end,
        "--baseline", "scripts/wave_baseline.json",
        "--runs-dir", str(runs), "--kpi-file", str(kpi_file),
    ])

    assert rc == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["iteration"] == 7
    assert printed["rows_closed"] == 3          # 4 baseline rows -> 1
    assert printed["worker_count"] == 2
    assert printed["repair_rate"] == 0.5        # 1 of 2 runs had repairs
    assert "window" in printed["phase_seconds"]
    lines = kpi_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == printed
```

- [ ] **Step 3: Run it — expect PASS** (this is characterization of existing behavior, not new code)

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS. If it fails, the test encodes a wrong expectation — fix the test, not the source.

- [ ] **Step 4: Commit**

```bash
git add tests/test_mine_iteration_kpis.py
git commit -m "test(kpis): characterize main() happy path (TEST signal, characterize-first)"
```

### Task 2: `main()` graceful degradation + unwritable output

**Files:**
- Test: `tests/test_mine_iteration_kpis.py` (append)

- [ ] **Step 1: Write the tests**

```python
def test_main_degrades_without_artifacts(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(m, "_derive_ci_wait_seconds", lambda repo: 0.0)
    kpi_file = tmp_path / "k.jsonl"
    rc = m.main([
        "--repo", str(tmp_path),
        "--runs-dir", str(tmp_path / "absent"),
        "--kpi-file", str(kpi_file),
    ])
    assert rc == 0
    kpi = json.loads(capsys.readouterr().out.strip())
    assert kpi["rows_closed"] == 0
    assert kpi["rows_per_hour"] == 0.0
    assert kpi["worker_count"] == 0
    assert kpi["phase_seconds"] == {}


def test_main_returns_one_when_kpi_path_is_a_directory(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(m, "_derive_ci_wait_seconds", lambda repo: 0.0)
    bad = tmp_path / "isadir"
    bad.mkdir()
    rc = m.main([
        "--repo", str(tmp_path),
        "--runs-dir", str(tmp_path / "absent"),
        "--kpi-file", str(bad),
    ])
    assert rc == 1
    assert "failed to append KPI line" in capsys.readouterr().err
```

- [ ] **Step 2: Run — expect PASS**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS (no `--start-sha`/`--end-sha` → empty phase/rows; opening a directory for append raises `IsADirectoryError` ⊂ `OSError` → exit 1).

- [ ] **Step 3: Commit**

```bash
git add tests/test_mine_iteration_kpis.py
git commit -m "test(kpis): characterize main() degradation + unwritable-output paths"
```

### Task 3: `_git_commit_epoch` + `_derive_phase_seconds`

**Files:**
- Test: `tests/test_mine_iteration_kpis.py` (append)

- [ ] **Step 1: Write the tests**

```python
def test_git_commit_epoch_valid_and_invalid(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    sha = _commit(repo, "a.txt", "x")
    assert isinstance(m._git_commit_epoch(repo, sha), float)
    assert m._git_commit_epoch(repo, "deadbeef") is None


def test_derive_phase_seconds_window_and_missing(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    a = _commit(repo, "a.txt", "x")
    b = _commit(repo, "a.txt", "y")
    ps = m._derive_phase_seconds(repo, a, b)
    assert "window" in ps and ps["window"] >= 0.0
    assert m._derive_phase_seconds(repo, None, b) == {}
    assert m._derive_phase_seconds(repo, a, "deadbeef") == {}
```

- [ ] **Step 2: Run — expect PASS**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_mine_iteration_kpis.py
git commit -m "test(kpis): characterize _git_commit_epoch + _derive_phase_seconds"
```

### Task 4: `_load_baseline_rows` (dict/missing) + `_derive_worker_runs`

**Files:**
- Test: `tests/test_mine_iteration_kpis.py` (append)

- [ ] **Step 1: Write the tests**

```python
def test_load_baseline_rows_dict_shapes_and_missing(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    sha = _commit(repo, "b.json", json.dumps({"x": [1, 2], "y": 5, "z": "skip"}))
    # list value -> len; int value -> value; other types ignored
    assert m._load_baseline_rows(repo, sha, "b.json") == {"x": 2, "y": 5}
    assert m._load_baseline_rows(repo, None, "b.json") == {}          # no sha
    assert m._load_baseline_rows(repo, sha, "missing.json") == {}     # git show fails


def test_derive_worker_runs_counts_repairs_and_missing_dir(tmp_path):
    runs = tmp_path / "runs"
    (runs / "p1").mkdir(parents=True)
    (runs / "p2").mkdir()
    (runs / "p1" / "repairs.txt").write_text("2", encoding="utf-8")
    (runs / "p2" / "repairs.txt").write_text("oops", encoding="utf-8")  # ValueError -> 0
    assert m._derive_worker_runs(runs) == [
        {"run": "p1", "repairs": 2},
        {"run": "p2", "repairs": 0},
    ]
    assert m._derive_worker_runs(tmp_path / "absent") == []
```

- [ ] **Step 2: Run — expect PASS**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_mine_iteration_kpis.py
git commit -m "test(kpis): characterize _load_baseline_rows (dict) + _derive_worker_runs"
```

### Task 5: `_derive_ci_wait_seconds` (both branches) + `mine_mprr_kpis` edges

**Files:**
- Test: `tests/test_mine_iteration_kpis.py` (append)

- [ ] **Step 1: Write the tests**

```python
def test_derive_ci_wait_seconds_success_and_failure(monkeypatch):
    class _R:
        stdout = json.dumps([{
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:05:00Z",
        }])
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: _R())
    assert m._derive_ci_wait_seconds(Path(".")) == 300.0

    def _boom(*a, **k):
        raise subprocess.SubprocessError("no gh")
    monkeypatch.setattr(m.subprocess, "run", _boom)
    assert m._derive_ci_wait_seconds(Path(".")) == 0.0


def test_mine_mprr_kpis_skips_blanks_and_counts_conflicts(tmp_path):
    ev = tmp_path / "e.jsonl"
    ev.write_text("\n".join([
        '{"event": "start", "id": "a"}',
        '',                                          # blank line skipped
        '{"event": "start", "id": "b"}',
        '{"event": "merge", "id": "a", "conflict": true}',
    ]) + "\n")
    kpi = m.mine_mprr_kpis(str(ev), ceiling=2)
    assert kpi["dispatched"] == 2
    assert kpi["merged"] == 1
    assert kpi["merge_conflict_rate"] == 1.0
    assert kpi["peak_concurrency"] == 2
```

- [ ] **Step 2: Run — expect PASS**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_mine_iteration_kpis.py
git commit -m "test(kpis): characterize _derive_ci_wait_seconds + mine_mprr_kpis edges"
```

### Checkpoint A: coverage clears the gate threshold

- [ ] **Step 1: Measure coverage of the file**

Run: `python3 -m pytest tests/ -q --cov=scripts --cov-report=term-missing 2>/dev/null | grep mine_iteration_kpis`
Expected: coverage **> 50%** (projected ~95%+), up from 38.4%. If still ≤ 50%, add tests for the lines listed under "Missing" before proceeding. (pytest-cov's per-file percent is the same number `coverage-gap-audit` reads from `coverage.json` — its `min_file_coverage = 50.0` is the authority, so clearing 50% here clears the freeze.)

- [ ] **Step 2: Full suite green**

Run: `python3 -m pytest tests/ -q`
Expected: all pass (was 246; now higher).

> The `scripts/`-scoped wave gate is still 20 here — Phase 1 unfreezes the 9, it does not remove them. Proceed to Phase 2.

---

## Phase 2 — Remediate the 9 now-unfrozen findings

### Task 6: SECURITY — inline `# nosec` (one commit)

**Files:**
- Modify: `scripts/mine_iteration_kpis.py:17,79,110,153,208`

- [ ] **Step 1: Suppress `B404` on the import (line 17)**

Change:
```python
import subprocess
```
to:
```python
import subprocess  # nosec B404: trusted git/gh, shell=False
```

- [ ] **Step 2: Annotate each `subprocess.run(` call (lines 79, 110, 153)**

> **Two verified constraints:** (1) bandit 1.9.4 splits nosec IDs on **whitespace**, not commas — `# nosec B603,B607` leaves **B603 unsuppressed** (3 issues survive). Use a **space**: `# nosec B603 B607`. (2) A trailing `# nosec` comment **cannot be auto-wrapped** by `ruff format`, so it must keep the line ≤ 88 cols — keep the reason terse.

On each of the three `subprocess.run(` opening lines, append (verified ≤ 88 cols):
```python
        out = subprocess.run(  # nosec B603 B607: fixed argv, shell=False
```
(for the `_derive_ci_wait_seconds` call the variable is also `out`; keep the existing variable name, only add the comment.)

- [ ] **Step 3: Justify the `/tmp` default (line 208)**

Change the `--runs-dir` default line to (terse — the verbose form is 103 cols → E501):
```python
        default=Path("/tmp/sp13/runs"),  # nosec B108: override via --runs-dir
```

- [ ] **Step 4: Verify bandit is clean for the file**

Run: `python3 -m bandit -q scripts/mine_iteration_kpis.py`
Expected: `No issues identified.` (if 3 `B603` survive, you used comma-separated IDs — switch to space-separated.)

- [ ] **Step 5: Verify the nosec comments introduced no E501**

Run: `ruff check scripts/mine_iteration_kpis.py --select E,W,F,B,SIM,UP --ignore F401,F811,F841,C901 && ruff format --check scripts/mine_iteration_kpis.py`
Expected: `All checks passed!` and `1 file already formatted`.

- [ ] **Step 6: Tests still green, then commit**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS.
```bash
git add scripts/mine_iteration_kpis.py
git commit -m "fix(kpis): annotate B404/B603/B607/B108 nosec (trusted git/gh, documented tmp default)"
```

### Task 7: TYPE — `cast` + `_repairs` helper (one commit)

**Files:**
- Modify: `scripts/mine_iteration_kpis.py` (imports, `compute_kpi` body, `is_regression` body)

- [ ] **Step 1: Add the `cast` import**

Change:
```python
from pathlib import Path
```
to:
```python
from pathlib import Path
from typing import cast
```

- [ ] **Step 2: Add a typed `_repairs` helper above `compute_kpi`**

```python
def _repairs(run: dict[str, object]) -> int:
    """Repair count for a worker run, coerced to int (untyped artifact field)."""
    value = run.get("repairs", 0)
    return value if isinstance(value, int) else 0
```

- [ ] **Step 3: Use it in `repair_rate` (replaces the line-41 expression)**

Change:
```python
    repair_rate = (
        sum(1 for run in worker_runs if (run.get("repairs") or 0) > 0)
        / len(worker_runs)
        if worker_runs
        else 0.0
    )
```
to:
```python
    repair_rate = (
        sum(1 for run in worker_runs if _repairs(run) > 0) / len(worker_runs)
        if worker_runs
        else 0.0
    )
```

- [ ] **Step 4: Cast the numeric reads in `is_regression` (lines 65-66)**

Change:
```python
    rph_drop = cur["rows_per_hour"] < prev["rows_per_hour"] * 0.8
    repair_rise = cur["repair_rate"] > prev["repair_rate"] * 1.5
```
to (already wrapped — the single-line cast form is 91/90 cols → E501; this is exactly what `ruff format` produces):
```python
    rph_drop = (
        cast(float, cur["rows_per_hour"]) < cast(float, prev["rows_per_hour"]) * 0.8
    )
    repair_rise = (
        cast(float, cur["repair_rate"]) > cast(float, prev["repair_rate"]) * 1.5
    )
```

- [ ] **Step 5: Verify mypy clean AND no new lint (the casts are long lines)**

Run: `ruff format scripts/mine_iteration_kpis.py && mypy scripts/mine_iteration_kpis.py && ruff check scripts/mine_iteration_kpis.py --select E,W,F,B,SIM,UP --ignore F401,F811,F841,C901`
Expected: `Success: no issues found in 1 source file` and `All checks passed!`. (If you wrote the casts on one line, `ruff format` rewrites them to the wrapped form above — do not skip it.)

- [ ] **Step 6: Tests green (casts/helper are runtime no-ops), then commit**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS.
```bash
git add scripts/mine_iteration_kpis.py
git commit -m "fix(kpis): resolve mypy operator/misc errors via _repairs helper + float casts"
```

### Task 8: COMPLEXITY — `KpiInputs` dataclass (one commit)

> Resolves `compute_kpi parameter_count` (6 > `max_params=5`). Safe: no callers exist outside this module + its test. **Alternative if you'd rather not change the signature:** add the row `{"leaf":"complexity","path":"scripts/mine_iteration_kpis.py","symbol":"compute_kpi","metric":"parameter_count"}` to `scripts/wave_baseline.json` with a `deferred-structural` justification in `scripts/wave_frozen.md` (per `references/prioritization.md` T4) — the gate clears either way. The dataclass is preferred.

**Files:**
- Modify: `scripts/mine_iteration_kpis.py` (imports, new dataclass, `compute_kpi` signature, `main()` call site)
- Modify: `tests/test_mine_iteration_kpis.py` (the one existing direct `compute_kpi` caller)

- [ ] **Step 1: Add the dataclass import**

Change:
```python
from __future__ import annotations

import argparse
```
to:
```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
```

- [ ] **Step 2: Define `KpiInputs` above `compute_kpi`**

```python
@dataclass(frozen=True)
class KpiInputs:
    """Already-mined inputs for one KPI record (groups compute_kpi's parameters)."""

    iteration: int
    rows_before: dict[str, int]
    rows_after: dict[str, int]
    phase_seconds: dict[str, float]
    worker_runs: list[dict[str, object]]
    ci_wait_seconds: float
```

- [ ] **Step 3: Re-point `compute_kpi` to the dataclass**

Change the signature and the first lines of the body:
```python
def compute_kpi(
    iteration: int,
    rows_before: dict[str, int],
    rows_after: dict[str, int],
    phase_seconds: dict[str, float],
    worker_runs: list[dict[str, object]],
    ci_wait_seconds: float,
) -> dict[str, object]:
```
to:
```python
def compute_kpi(inputs: KpiInputs) -> dict[str, object]:
```
Then, as the first statement inside the function (before `rows_closed = ...`), unpack:
```python
    iteration = inputs.iteration
    rows_before = inputs.rows_before
    rows_after = inputs.rows_after
    phase_seconds = inputs.phase_seconds
    worker_runs = inputs.worker_runs
    ci_wait_seconds = inputs.ci_wait_seconds
```
(The rest of the body and the returned dict are unchanged.)

- [ ] **Step 4: Update the `main()` call site**

Change:
```python
    kpi = compute_kpi(
        iteration=args.iteration,
        rows_before=rows_before,
        rows_after=rows_after,
        phase_seconds=phase_seconds,
        worker_runs=worker_runs,
        ci_wait_seconds=ci_wait_seconds,
    )
```
to:
```python
    kpi = compute_kpi(
        KpiInputs(
            iteration=args.iteration,
            rows_before=rows_before,
            rows_after=rows_after,
            phase_seconds=phase_seconds,
            worker_runs=worker_runs,
            ci_wait_seconds=ci_wait_seconds,
        )
    )
```

- [ ] **Step 5: Update the existing direct caller in the test**

In `tests/test_mine_iteration_kpis.py`, change `test_rows_per_hour_from_counts_and_duration`'s call from:
```python
    kpi = m.compute_kpi(
        iteration=5,
        rows_before={"repo-a": 40, "repo-b": 7},
        rows_after={"repo-a": 36, "repo-b": 7},
        phase_seconds={"diagnosis": 120.0, "execution": 3480.0, "ship": 600.0},
        worker_runs=[{"repairs": 1}, {"repairs": 0}, {"repairs": 0}],
        ci_wait_seconds=300.0,
    )
```
to:
```python
    kpi = m.compute_kpi(m.KpiInputs(
        iteration=5,
        rows_before={"repo-a": 40, "repo-b": 7},
        rows_after={"repo-a": 36, "repo-b": 7},
        phase_seconds={"diagnosis": 120.0, "execution": 3480.0, "ship": 600.0},
        worker_runs=[{"repairs": 1}, {"repairs": 0}, {"repairs": 0}],
        ci_wait_seconds=300.0,
    ))
```

- [ ] **Step 6: Verify the complexity finding is gone, lint/format/mypy clean, tests green**

Run: `ruff format scripts/mine_iteration_kpis.py && python3 -m lizard scripts/mine_iteration_kpis.py | grep compute_kpi`
Expected: the `PARAM` column for `compute_kpi` is `1` (≤ 5). (The new `KpiInputs` class is a dataclass, not a >5-param function, so it adds no finding.)
Run: `mypy scripts/mine_iteration_kpis.py && ruff check scripts/mine_iteration_kpis.py --select E,W,F,B,SIM,UP --ignore F401,F811,F841,C901`
Expected: `Success: no issues found` and `All checks passed!`.
Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/mine_iteration_kpis.py tests/test_mine_iteration_kpis.py
git commit -m "refactor(kpis): group compute_kpi params into KpiInputs (param_count 6 -> 1)"
```

### Checkpoint B: gate 20 → 11

- [ ] **Step 1: Re-run the convergence gate**

Run:
```bash
WAVE_RUNNER="$PWD/scripts/run_diagnosis_wave.py" \
SKILLS_ROOT=/home/jakub/projects/repo-audit-skills/skills \
python3 scripts/check_wave_baseline.py
```
Expected: `status: fail`, **new = 11**, stale = 0. All 9 `scripts/mine_iteration_kpis.py` rows are gone. The remaining 11 are the other-file/structural items (`mprr_normalize` MI, `mprr_integrate` B603, `synthesize_perf` B105/index, `synth_run` arg-type ×2, `_wave_findings` dict-item, 3× growth, 1× hotspot) — out of scope for this plan.

- [ ] **Step 2: Lint/format/full-suite green**

Run: `ruff check scripts/ --select E,W,F,B,SIM,UP --ignore F401,F811,F841,C901 && ruff format --check scripts/ && python3 -m pytest tests/ -q`
Expected: all clean/pass.

---

## Phase 3 — Ship (patch release)

> No behavior change anywhere (tests, nosec, casts, internal dataclass) → **patch**: 0.7.1 → 0.7.2.

### Task 9: Version bump, release, reinstall

**Files:**
- Modify: `SKILL.md` (frontmatter `version`), `CHANGELOG.md`

- [ ] **Step 1: Bump version**

In `SKILL.md` change `version: 0.7.1` → `version: 0.7.2`. In `CHANGELOG.md` add under the `# Changelog` heading:
```markdown
## 0.7.2

chore(kpis): characterize `scripts/mine_iteration_kpis.py` (coverage 38.4% -> >50%, the
coverage-gate keystone) and remediate its 9 wave findings — inline `# nosec`
(B404/B603/B607/B108, trusted git/gh + documented tmp default), mypy operator/misc fixes
via a `_repairs` helper + float casts, and a `KpiInputs` dataclass (compute_kpi param_count
6 -> 1). No behavior change. Self-audit convergence gate 20 -> 11.
```

- [ ] **Step 2: Release gate + full suite**

Run: `python3 scripts/check_release.py && python3 -m pytest tests/ -q`
Expected: `{"status": "pass"}` and all tests pass.

- [ ] **Step 3: Commit, merge to main, tag, push**

```bash
git add -A && git commit -m "chore(release): kpis convergence + mechanical fixes (0.7.1 -> 0.7.2)"
git checkout main && git merge --no-ff feat/kpis-convergence -m "Merge feat/kpis-convergence: mine_iteration_kpis convergence (v0.7.2)"
git tag -a v0.7.2 -m "v0.7.2 — mine_iteration_kpis characterized + remediated; gate 20 -> 11"
git push origin main && git push origin v0.7.2
```

- [ ] **Step 4: Reinstall the released tree into the live skills root**

```bash
DEST=~/.claude/skills/repo-audit-refactor-optimize
TMP=$(mktemp -d)
git archive --format=tar main | (cd "$TMP" && tar -xf -)
rsync -a --delete "$TMP/" "$DEST/" && rm -rf "$TMP"
grep -m1 '^version:' "$DEST/SKILL.md"   # expect 0.7.2
```

---

## Follow-on (separate plans, not this one)

1. **Other-file remediation** (gate 11 → ~6): `synth_run`/`synthesize_perf`/`_wave_findings` TYPE fixes; `mprr_integrate` B603 + `synthesize_perf` B105 security — best fixed by **authoring `scripts/security_audit_config.json`** (the file `check_wave_baseline.py` already references but that doesn't exist), which also retires this plan's inline-nosec choice if you prefer central config.
2. **Structural/policy** (gate ~6 → 0): ratchet `mprr_normalize` MI + `references/pipeline.md` hotspot into the baseline+ledger; **re-anchor `scripts/wave_anchor.txt`** + refresh `scripts/growth_allowances.json` to clear the 3 growth findings (they cannot be remediated by editing code).
3. **Hygiene:** reconcile `scripts/wave_frozen.md` (says 7) to the real 13-row `scripts/wave_baseline.json`; wire `check_wave_baseline.py` into CI.

---

## Self-Review

**Spec coverage:** All 9 file findings are addressed — 4 SECURITY (Task 6), 4 TYPE (Task 7), 1 COMPLEXITY (Task 8); the freeze that blocks them is lifted first (Tasks 1-5 + Checkpoint A). Gate delta 20→11 verified at Checkpoint B. Ship is Phase 3. ✓

**Placeholder scan:** Every code step shows complete code; every command has expected output. No TBD/"handle edge cases"/"similar to". ✓

**Type/name consistency:** `KpiInputs` (Task 8) is defined before use; `compute_kpi(inputs: KpiInputs)` matches the `main()` call site and the updated test; `_repairs` (Task 7) is defined before its use in `compute_kpi`. The Task 7 line-41 edit and the Task 8 body-unpack edit touch the same function but different lines (predicate vs. signature/first-statements) and compose cleanly in order. ✓

**Ordering risk:** Phase 1 must land before Phase 2 (coverage gate). Task 7 adds `_repairs`/`cast`; Task 8 changes the signature and unpacks at the top — applying 7 then 8 leaves `repair_rate` using `_repairs(run)` over the unpacked `worker_runs`, which is correct. ✓
