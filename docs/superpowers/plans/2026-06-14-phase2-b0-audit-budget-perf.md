# Phase 2 · B0 — Audit-Budget Perf Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Profile repo-A's `npm run check` (coverage 188.5 s + full-pytest 183.4 s ≈ 372 s), apply exactly ONE bounded perf-optimization win measured identically before/after, record a verified win (≥5% median, suite green) OR an honest no-win, ship via the Phase-1 pipeline only if a win touches a shipped repo, then correct the stale roadmap B0 text and record the perf-smell-narrowing deferral.

**Architecture:** Measure-then-decide. Task 1 establishes a perf-benchmark baseline + deterministic per-gate/per-suite attribution. Task 2 applies a deterministic decision rule to pick ONE of four pre-written candidates (C1 drop redundant second test run · C2 intra-suite xdist on the long pole · C3 longest-processing-time suite scheduling · C4 sysmon coverage). Task 3 applies only the selected candidate (each is fully spelled out). Task 4 re-measures identically and runs `verify_win.py`. Task 5 branches on the verdict. Tasks 6–9 ship-or-record, correct docs, and close out.

**Tech Stack:** Python 3.14, pytest, coverage.py, `perf-benchmark` (`scripts/perf_benchmark_pipeline.py`), `perf-optimization` (`scripts/verify_win.py`), repo-A gate runner (`scripts/run_checks.py`), git + `gh`.

**Spec:** `docs/superpowers/specs/2026-06-14-phase2-b0-audit-budget-perf-design.md`

---

## Repo / path conventions

- **repo-A** = `/home/jakub/projects/repo-audit-skills` (gate scripts live here; the likely-touched repo)
- **repo-B** = `/home/jakub/projects/repo-audit-refactor-optimize` (campaign/roadmap home; this plan + spec live here)
- **repo-P** = `/home/jakub/projects/perf-benchmark-skill` (perf-benchmark + perf-optimization skills live here)
- **PB** = `python3 /home/jakub/projects/perf-benchmark-skill/scripts/perf_benchmark_pipeline.py`
- **VW** = `python3 /home/jakub/projects/perf-benchmark-skill/perf-optimization/scripts/verify_win.py`
- Artifacts dir (gitignored scratch, NOT committed): `/tmp/b0/`
- Committed evidence dir (repo-B): `docs/superpowers/b0-evidence/`

---

## File Structure

| File | Repo | Responsibility | Touched by |
|------|------|----------------|------------|
| `scripts/run_checks.py` | A | gate runner (`HEAVY`/`CHEAP` lists, timings) | C1, C3 |
| `scripts/check_full_pytest.py` | A | plain-pytest gate (the redundant second run) | C1, C2, C3 |
| `scripts/check_coverage_gap.py` | A | coverage gate (authoritative green + ratchet) | C2, C3, C4 |
| `scripts/check_budget.json` | A | per-gate second budgets | C1 |
| `tests/test_check_full_pytest.py` | A | tests for the plain-pytest gate | C1, C2, C3 |
| `tests/test_run_checks.py` | A | tests for the gate runner | C1, C3 |
| `tests/test_check_coverage_gap.py` | A | tests for the coverage gate | C2, C3, C4 |
| `pyproject.toml` | A | dev deps (only if C2 adds pytest-xdist) | C2 |
| `docs/superpowers/b0-evidence/*` | B | committed baseline/after/verdict JSON + notes | Tasks 1,4,5 |
| `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md` | B | roadmap B0 text correction | Task 8 |
| `repo-audit-skills/docs/superpowers/SP15-CANDIDATES.md` | A | perf-smell deferral record | Task 7 |

---

## Task 0: Branch setup + green baseline confirmation

**Files:** none (git + verification only)

- [ ] **Step 1: Confirm repo-B branch (already created during brainstorming)**

Run:
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git branch --show-current
```
Expected: `feat/phase2-b0`. If not, `git checkout feat/phase2-b0`.

- [ ] **Step 2: Create repo-A work branch from clean main**

Run:
```bash
cd /home/jakub/projects/repo-audit-skills && git status --short && git checkout main && git pull --ff-only 2>/dev/null; git checkout -b feat/phase2-b0 && git branch --show-current
```
Expected: clean working tree, then `feat/phase2-b0`. If the branch exists, `git checkout feat/phase2-b0`.

- [ ] **Step 3: Confirm repo-A is GREEN before measuring (baseline must be from a passing state)**

Run:
```bash
cd /home/jakub/projects/repo-audit-skills && npm run check
```
Expected: exit 0, summary `gates: 10/10 cheap, 2/2 heavy, 0 over-budget, 0 failed`. If RED, STOP — fix/triage the red gate first (do not benchmark a broken tree). Capture `scripts/check_timings.json`.

- [ ] **Step 4: Create scratch + evidence dirs**

Run:
```bash
mkdir -p /tmp/b0 && mkdir -p /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b0-evidence
```
Expected: both dirs exist.

---

## Task 1: Baseline measurement (perf-benchmark self-application #1)

**Files:**
- Create: `/tmp/b0/baseline/` (perf-benchmark out-dir), `/tmp/b0/ledger.jsonl`
- Create: `docs/superpowers/b0-evidence/baseline-summary.json`, `docs/superpowers/b0-evidence/per-suite-timings.json` (repo-B)

- [ ] **Step 1: Capture deterministic per-gate attribution (free — run_checks already writes it)**

The Step-0.3 run already wrote `repo-audit-skills/scripts/check_timings.json`. Copy it as evidence:
```bash
cp /home/jakub/projects/repo-audit-skills/scripts/check_timings.json /tmp/b0/check_timings_baseline.json && cat /tmp/b0/check_timings_baseline.json
```
Expected: JSON with `coverage` ≈ 185–190, `pytest` ≈ 180–185, all cheap gates < 3.

- [ ] **Step 2: Capture per-suite attribution (which suite is the long pole?)**

Run a throwaway per-suite timing of the plain-pytest path (no source changes):
```bash
cd /home/jakub/projects/repo-audit-skills && python3 - <<'PY'
import json, subprocess, sys, time
from pathlib import Path
ROOT = Path("/home/jakub/projects/repo-audit-skills")
dirs = [ROOT/"tests"] + sorted(p for p in ROOT.glob("skills/*/tests") if p.is_dir())
rows = []
for d in dirs:
    t = time.perf_counter()
    p = subprocess.run([sys.executable,"-m","pytest",str(d),"-q","--color=no","-p","no:cacheprovider"],
                       cwd=d.parent, capture_output=True, text=True)
    rows.append({"suite": str(d.relative_to(ROOT)), "sec": round(time.perf_counter()-t,2), "rc": p.returncode})
rows.sort(key=lambda r: -r["sec"])
Path("/tmp/b0/per-suite-timings.json").write_text(json.dumps(rows, indent=2))
for r in rows[:8]: print(f'{r["sec"]:8.2f}s  rc={r["rc"]}  {r["suite"]}')
print("TOTAL serial:", round(sum(r["sec"] for r in rows),1), "s")
PY
```
Expected: a sorted table; note the top suite's share of the total. This is **serial** time; the gate runs these in parallel so wall ≈ max(top suites given `cpu-1` slots). Record which suite dominates.

- [ ] **Step 3: perf-benchmark baseline of the heavy workload (p50 + ledger + fingerprint)**

Benchmark the user-facing gate runner (currently green → exits 0). Keep reps low (long, low-variance workload):
```bash
cd /home/jakub/projects/repo-audit-skills && python3 /home/jakub/projects/perf-benchmark-skill/scripts/perf_benchmark_pipeline.py \
  --root /home/jakub/projects/repo-audit-skills \
  --out-dir /tmp/b0/baseline \
  --target "python3 scripts/run_checks.py" \
  --tier fast --time-repeats 3 --max-cv 5.0 \
  --baseline-ledger /tmp/b0/ledger.jsonl
```
Expected: `/tmp/b0/baseline/benchmark_summary.json` exists with `wall_time_percentiles.p50` ≈ 370–380 and `environment` populated; ledger appended.
**Fallback:** if the tool rejects a target without `{SIZE}`, append `--sizes 1` and use target `"python3 scripts/run_checks.py"` (the `{SIZE}` is unused) — or benchmark the single heavy gate `"python3 scripts/check_coverage_gap.py"`. If the wall-time dimension scores `N/A (noise)`, raise `--time-repeats` to 5. Record the exact command actually used in the evidence note.

- [ ] **Step 4: Persist baseline evidence to repo-B**

Run:
```bash
cp /tmp/b0/baseline/benchmark_summary.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b0-evidence/baseline-summary.json
cp /tmp/b0/per-suite-timings.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b0-evidence/per-suite-timings.json
cp /tmp/b0/check_timings_baseline.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b0-evidence/check-timings-baseline.json
```
Expected: three files copied.

- [ ] **Step 5: Commit baseline evidence (repo-B)**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b0-evidence/ && git commit -m "perf(b0): baseline — per-gate/per-suite attribution + perf-benchmark p50

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
Expected: commit created.

---

## Task 2: Apply the decision rule → select ONE candidate

**Files:** Create `docs/superpowers/b0-evidence/decision.md` (repo-B)

- [ ] **Step 1: Read the attribution and classify the bottleneck**

From `per-suite-timings.json` + `check-timings-baseline.json`, compute:
- **double-run share** = `pytest_gate_sec / (coverage_gate_sec + pytest_gate_sec)` (expected ≈ 0.49).
- **long-pole share** = `top_suite_serial_sec / total_serial_sec`.

- [ ] **Step 2: Select per the spec §6 decision rule (record the choice + reason in decision.md)**

```
IF double-run share ≈ 0.49 (it is, structurally) AND the "tests-run-uninstrumented" signal
   is judged acceptable to drop  ->  C1  (highest ceiling ~183s)
ELIF one suite is a clear long pole (long-pole share ≳ 0.5)
       AND C1's tradeoff is judged too structural:
         ->  C2 if adding pytest-xdist is acceptable, else C3
ELSE (cost evenly spread, no single high-ceiling lever)
   ->  C3 if it plausibly clears 5%, else go straight to an honest no-win (Task 5B)
```
Write `decision.md` with: the two shares, the selected candidate ID, one paragraph of reasoning, and the predicted ceiling. **Only ONE candidate proceeds.** Commit:
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b0-evidence/decision.md && git commit -m "perf(b0): record candidate decision (measure-then-decide)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

> **Reviewer gate:** the two-stage review MUST confirm the selected candidate matches the recorded shares before Task 3 proceeds.

---

## Task 3: Apply the selected candidate (run EXACTLY ONE sub-task)

All sub-tasks operate in **repo-A** on `feat/phase2-b0`. Pick the one chosen in Task 2.

### Task 3-C1: Drop the redundant second (uninstrumented) test run

**Rationale:** `check_full_pytest.py` re-runs all 20 suites for a pass/fail the coverage gate already enforces (it fails on any suite `rc != 0`, lines 187–190) and has no baseline ratchet of its own. Coverage becomes the authoritative green gate.

**Files:**
- Modify: `scripts/run_checks.py` (remove the `pytest` entry from `HEAVY`)
- Modify: `scripts/check_budget.json` (remove the `pytest` key)
- Delete: `scripts/check_full_pytest.py`, `tests/test_check_full_pytest.py`
- Modify: `tests/test_run_checks.py` (drop assertions referencing the `pytest` gate)
- Grep + fix any doc/SKILL reference to the removed gate

- [ ] **Step 1: Write/adjust the failing test in `tests/test_run_checks.py`**

Add a test asserting `HEAVY` no longer contains `pytest` and contains only `coverage`:
```python
def test_heavy_gates_are_coverage_only():
    from scripts.run_checks import HEAVY
    names = [name for name, _ in HEAVY]
    assert names == ["coverage"], names
```
- [ ] **Step 2: Run it — verify it FAILS**

Run: `cd /home/jakub/projects/repo-audit-skills && python3 -m pytest tests/test_run_checks.py::test_heavy_gates_are_coverage_only -q`
Expected: FAIL (HEAVY still has `pytest`).

- [ ] **Step 3: Remove the pytest gate from the runner**

In `scripts/run_checks.py`, change `HEAVY` to:
```python
HEAVY: list[tuple[str, str]] = [
    ("coverage", "scripts/check_coverage_gap.py"),
]
```
- [ ] **Step 4: Remove the `pytest` budget key**

In `scripts/check_budget.json`, delete the `"pytest": 260,` line (keep `"coverage": 270`).

- [ ] **Step 5: Delete the redundant gate + its test**

Run:
```bash
cd /home/jakub/projects/repo-audit-skills && git rm scripts/check_full_pytest.py tests/test_check_full_pytest.py
```
- [ ] **Step 6: Drop dangling references in `tests/test_run_checks.py`**

Remove any assertion/import that references `pytest` as a heavy gate or `check_full_pytest`. Re-read the file and excise only those lines.

- [ ] **Step 7: Sweep for stale references**

Run:
```bash
cd /home/jakub/projects/repo-audit-skills && git grep -n "check_full_pytest\|full_pytest_snapshot\|\"pytest\"" -- ':!docs/audits' ':!docs/superpowers'
```
Fix any live reference (SKILL.md, README, scripts). `docs/audits/*` historical reports are immutable — leave them.

- [ ] **Step 8: Run the affected tests — verify GREEN**

Run: `cd /home/jakub/projects/repo-audit-skills && python3 -m pytest tests/test_run_checks.py -q`
Expected: PASS including the new `test_heavy_gates_are_coverage_only`.

- [ ] **Step 9: Commit**

```bash
cd /home/jakub/projects/repo-audit-skills && git add -A && git commit -m "perf(check): drop redundant uninstrumented pytest gate (coverage gate is authoritative green)

The coverage gate already fails on any suite rc!=0 and ratchets coverage-gap
findings; the plain-pytest gate re-ran all 20 suites for a duplicate pass/fail
with no baseline of its own. Removing it halves the heavy-gate wall time.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3-C2: Intra-suite parallelism (pytest-xdist) on the long-pole suite

**Rationale:** if one suite dominates wall time while cores idle at the tail, parallelise *within* it. Scope xdist to the long-pole suite(s) only so total workers don't exceed cores.

**Files:**
- Modify: `pyproject.toml` (add `pytest-xdist` to dev deps)
- Modify: `scripts/check_full_pytest.py` and `scripts/check_coverage_gap.py` (pass `-n` for the long-pole suite)
- Modify: `.github/workflows/check.yml` if it pins/install deps (ensure xdist installed in CI)
- Test: `tests/test_check_full_pytest.py`, `tests/test_check_coverage_gap.py`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml` dev/test extras add `pytest-xdist>=3.6`. Install: `cd /home/jakub/projects/repo-audit-skills && pip install -e '.[dev]'` (or the project's documented dev-install). Confirm `python3 -m pytest --version` lists xdist.

- [ ] **Step 2: Write the failing test (long-pole suite gets `-n`)**

In `tests/test_check_full_pytest.py`, add a test that `run_suite` builds an `-n` argument for the designated heavy suite (constant `XDIST_SUITES`):
```python
def test_long_pole_suite_uses_xdist(monkeypatch):
    import scripts.check_full_pytest as m
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        class R: returncode = 0; stdout = "1 passed"; stderr = ""
        return R()
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    m.run_suite(m.ROOT / next(iter(m.XDIST_SUITES)))
    assert "-n" in captured["cmd"]
```
- [ ] **Step 3: Run it — verify FAIL** (`XDIST_SUITES` undefined / no `-n`).

Run: `cd /home/jakub/projects/repo-audit-skills && python3 -m pytest tests/test_check_full_pytest.py::test_long_pole_suite_uses_xdist -q` → FAIL.

- [ ] **Step 4: Implement scoped xdist**

In `scripts/check_full_pytest.py` add near the top a frozen set of the long-pole suite path(s) identified in Task 1 (e.g. `XDIST_SUITES = {"skills/test-redundancy-triage/tests"}`) and, in `run_suite`, append `["-n", "auto"]` (or a fixed small N) only when `str(suite.relative_to(ROOT)) in XDIST_SUITES`. Mirror the same scoped change in `check_coverage_gap.py::_run_one_suite`. Ensure outer-pool workers × inner N does not exceed cores (cap inner N so the long pole, which runs near-alone at the tail, uses spare cores).

- [ ] **Step 5: Run affected tests — verify GREEN**

Run: `cd /home/jakub/projects/repo-audit-skills && python3 -m pytest tests/test_check_full_pytest.py tests/test_check_coverage_gap.py -q` → PASS.

- [ ] **Step 6: Commit** (`git add -A && git commit -m "perf(check): scoped pytest-xdist on the long-pole suite" ...` with the Co-Authored-By trailer).

### Task 3-C3: Longest-processing-time suite scheduling (zero-dependency)

**Rationale:** start the long pole first so `ThreadPoolExecutor` keeps cores busy; pure ordering, no semantics change.

**Files:**
- Modify: `scripts/check_full_pytest.py::suite_dirs` and `scripts/check_coverage_gap.py` (`SUITES` order)
- Test: `tests/test_check_full_pytest.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_check_full_pytest.py`:
```python
def test_suites_scheduled_longest_first():
    import scripts.check_full_pytest as m
    dirs = [str(p.relative_to(m.ROOT)) for p in m.suite_dirs()]
    assert dirs[0] == "skills/test-redundancy-triage/tests"  # the measured long pole
```
(Substitute the actual long-pole suite from Task 1 if different.)

- [ ] **Step 2: Run it — verify FAIL.** Run the node above → FAIL.

- [ ] **Step 3: Implement LPT ordering**

Add a module constant `SUITE_ORDER` (the Task-1 per-suite ranking, longest first) and sort `suite_dirs()`’s result and the `SUITES` list by that ranking (unknown suites sort last, stable). Keep the result deterministic (byte-stable snapshot still holds because results are re-sorted by suite path before writing).

- [ ] **Step 4: Run affected tests — verify GREEN.** → PASS.

- [ ] **Step 5: Commit** (`perf(check): schedule suites longest-first (LPT) to fill idle cores` + trailer).

### Task 3-C4: `COVERAGE_CORE=sysmon` on the coverage gate (expected no-win — confirm)

**Files:** Modify `scripts/check_coverage_gap.py::suite_env`; Test `tests/test_check_coverage_gap.py`

- [ ] **Step 1: Write failing test** asserting `suite_env(...)["COVERAGE_CORE"] == "sysmon"`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3:** In `suite_env`, add `"COVERAGE_CORE": "sysmon"` to the returned env dict.
- [ ] **Step 4: Run affected tests → GREEN.**
- [ ] **Step 5: Commit** (`perf(check): use sys.monitoring coverage core (py3.12+)` + trailer). *Expected to be sub-threshold at Task 4 → honest no-win.*

---

## Task 4: Re-measure identically + verify_win verdict

**Files:** Create `/tmp/b0/after/`, `docs/superpowers/b0-evidence/after-summary.json`, `docs/superpowers/b0-evidence/verdict.json` (repo-B)

- [ ] **Step 1: Confirm the family suite is still GREEN after the change**

Run: `cd /home/jakub/projects/repo-audit-skills && python3 -m pytest -q -p no:cacheprovider` over the changed suites (or `npm run check`). Capture the exit code as `SUITE_RC` (must be 0 to accept a win).

- [ ] **Step 2: Re-run perf-benchmark with the IDENTICAL command from Task 1 Step 3**

Use the exact target/flags recorded in the baseline evidence note (same machine/session/governor):
```bash
cd /home/jakub/projects/repo-audit-skills && python3 /home/jakub/projects/perf-benchmark-skill/scripts/perf_benchmark_pipeline.py \
  --root /home/jakub/projects/repo-audit-skills \
  --out-dir /tmp/b0/after \
  --target "python3 scripts/run_checks.py" \
  --tier fast --time-repeats 3 --max-cv 5.0 \
  --baseline-ledger /tmp/b0/ledger.jsonl
```
Expected: `/tmp/b0/after/benchmark_summary.json` with a lower `p50` (for a real win).

- [ ] **Step 3: Run the acceptance ratchet**

```bash
python3 /home/jakub/projects/perf-benchmark-skill/perf-optimization/scripts/verify_win.py \
  --before /tmp/b0/baseline/benchmark_summary.json \
  --after  /tmp/b0/after/benchmark_summary.json \
  --suite-exit-code "$SUITE_RC" \
  --min-win 5.0 \
  --ledger /tmp/b0/ledger.jsonl \
  --out /tmp/b0/verdict.json && echo "VERDICT=accept" || echo "VERDICT=reject"
```
Read `/tmp/b0/verdict.json` — do NOT trust only the shell exit. Note `verdict`, `median_win_percent`, `reasons`.

- [ ] **Step 4: Persist after/verdict evidence to repo-B + commit**

```bash
cp /tmp/b0/after/benchmark_summary.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b0-evidence/after-summary.json
cp /tmp/b0/verdict.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b0-evidence/verdict.json
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b0-evidence/ && git commit -m "perf(b0): after-summary + verify_win verdict

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Branch on the verdict

### Task 5A: verdict == accept → proceed to ship (Task 6)

- [ ] **Step 1:** Append the win to `decision.md` (median win %, before/after p50, candidate). Commit. Proceed to Task 6.

### Task 5B: verdict == reject / honest no-win → revert + record

- [ ] **Step 1: Revert the repo-A candidate change** (keep the tree green; the change did not earn its place):
```bash
cd /home/jakub/projects/repo-audit-skills && git checkout main -- . 2>/dev/null; git status --short
```
Or `git reset --hard` the candidate commit(s) on `feat/phase2-b0` back to the pre-Task-3 state. Re-confirm `npm run check` green.

- [ ] **Step 2: Record the honest no-win** per `perf-benchmark-skill/perf-optimization/references/optimization-playbook.md`: write `docs/superpowers/b0-evidence/NO-WIN.md` (repo-B) with the candidate, the measured median win %, the `reasons`, and the conclusion that repo-A's heavy gates remain within budget (coverage 188.5 < 270, pytest 183.4 < 260) so no change is warranted now. Commit. **Skip Task 6** (nothing ships). Proceed to Task 7.

---

## Task 6: Ship the win via the Phase-1 pipeline (only if 5A)

Ship order **repo-A → repo-B → repo-P**. Only repos whose tracked content changed get a release. (If the win is repo-A-local, repo-B/repo-P releases may be unnecessary — but repo-B's roadmap/evidence/SP15 doc edits still merge to repo-B `main`.)

- [ ] **Step 1: repo-A version bump** — `package.json` `0.7.2 → 0.7.3` AND all 19 leaf `SKILL.md` version lines. Dated `CHANGELOG.md` entry (date == commit date `2026-06-14`). Then read back:
```bash
cd /home/jakub/projects/repo-audit-skills && git add -A && git commit -m "chore(release): family 0.7.2 -> 0.7.3 (Phase 2 B0 audit-budget win)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" && git show HEAD:package.json | grep version && git show HEAD:CHANGELOG.md | head -5
```
- [ ] **Step 2: repo-A local gate sim + fresh-clone sim** — `npm ci` in a fresh clone of the branch, run `npm run check` → green. Read the gate JSON, do not trust piped exit.
- [ ] **Step 3: repo-A merge → main, push, tag, release**
```bash
cd /home/jakub/projects/repo-audit-skills && git checkout main && git merge --no-ff feat/phase2-b0 -m "Merge feat/phase2-b0: B0 audit-budget perf win" && git push origin main && git tag v0.7.3 && git push origin v0.7.3 && gh release create v0.7.3 --title v0.7.3 --notes "Phase 2 B0 audit-budget perf win"
```
- [ ] **Step 4: repo-A growth re-baseline** — AFTER push, confirm `npm run check` growth gate green against the new tag.
- [ ] **Step 5: repo-A reinstall** — rsync the skills to `~/.claude/skills/` per the family's install convention.
- [ ] **Step 6: repo-B/repo-P pin bumps (only if repo-A leaf tag is a gate pin they consume AND behaviour changed)** — bump `.github/workflows/*.yml` leaf pin `v0.7.2 → v0.7.3`; keep `fetch-depth: 0` on the `convergence-gate` checkout. For repo-P run `~/.local/bin/ruff format --check scripts/ tests/` + `ruff check scripts/ tests/` locally before pushing. repo-B CHANGELOG is dateless; repo-P CHANGELOG is dated. Read back each bump via `git show HEAD:<file>`.
- [ ] **Step 7: Verify REAL CI green on every pushed commit, incl. `convergence-gate`**
```bash
for r in repo-audit-skills repo-audit-refactor-optimize perf-benchmark-skill; do cd /home/jakub/projects/$r && echo "== $r ==" && gh run list --branch main --limit 3; done
```
Expected: latest runs `success`. If the gate is red: `gh run view <id> --log-failed`, fix, do not leave a red gate.

---

## Task 7: Record the perf-smell-narrowing deferral

**Files:** Modify `repo-audit-skills/docs/superpowers/SP15-CANDIDATES.md` (repo-A, on `feat/phase2-b0` if not yet merged, else a tiny follow-up branch)

- [ ] **Step 1:** Sharpen the last bullet (the perf-smell narrowing standing candidate) to add a dated note: *"B0 (2026-06-14) considered and DEFERRED this: it is NOT on the wall-clock critical path (the family's 372 s floor is repo-A's coverage + full-pytest gates, not the perf-smell lane, which runs inside the already-fast Tier-1 wave), and it is a coordinated multi-repo change (leaf re-version → re-pin repo-B/repo-P gate tags → prune 77 accepts → reconverge → update leaf tests) that needs its own brainstorm → plan → ship. Improves convergence honesty, not B0's budget."*
- [ ] **Step 2: Commit** (`docs(sp15): record B0 deferral of perf-smell narrowing` + trailer). If repo-A already merged/released in Task 6, this rides a follow-up commit to main (doc-only, no release needed) or is folded into the Task-6 branch before merge.

---

## Task 8: Correct the stale roadmap B0 text

**Files:** Modify `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md:331` (repo-B, `feat/phase2-b0`)

- [ ] **Step 1: Replace line 331** the stale B0 bullet with:

> **B0 (prerequisite): bring the family's full audit under budget.** Profile repo-A's `npm run check` with `perf-benchmark` — the cost is the **coverage gate (188.5 s) + full-pytest gate (183.4 s)** running the 20 leaf suites (the heaviest is `test-redundancy-triage`, ~220 tests); coverage instrumentation adds only ~5 s, so the lever is the **double test run**, not a probe. (There is no bootstrap probe; the only 300 s timeout is the coverage-gap *leaf-audit* subprocess in `check_coverage_gap.py`. The Tier-1 wave is 9-lane and fast.) Apply one bounded `perf-optimization` win (or honestly record no-win) per `docs/superpowers/specs/2026-06-14-phase2-b0-audit-budget-perf-design.md`. **First self-application of `perf-benchmark`/`perf-optimization` on the family.**

- [ ] **Step 2: Verify no stale tokens remain**

Run: `cd /home/jakub/projects/repo-audit-refactor-optimize && grep -n "bootstrap-probe\|8-lane" docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md`
Expected: no matches (the only remaining "300s"/"probe" mentions are the corrected explanation).

- [ ] **Step 3: Commit** (`docs(roadmap): correct stale B0 text (no bootstrap-probe; 9-lane fast wave; real cost = coverage+pytest double run)` + trailer).

---

## Task 9: Close out — merge repo-B, update memory, final verification, STOP

- [ ] **Step 1: Merge repo-B `feat/phase2-b0` → main** (spec + plan + evidence + roadmap correction + SP15 note if it lived here):
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git checkout main && git merge --no-ff feat/phase2-b0 -m "Merge feat/phase2-b0: B0 audit-budget perf (spec, plan, evidence, roadmap fix)" && git push origin main
```
- [ ] **Step 2: Final verification checklist (spec §9 Definition of Done)** — confirm each box:
  - baseline + after + verdict artifacts committed in `docs/superpowers/b0-evidence/`;
  - exactly one candidate applied, verdict recorded (accept OR honest no-win);
  - if accept + shipped: all three mains CI-green incl. `convergence-gate`; tagged + released + reinstalled; CHANGELOG read back;
  - perf-smell deferral recorded in `SP15-CANDIDATES.md`;
  - roadmap B0 text corrected (no `bootstrap-probe`/`8-lane`);
- [ ] **Step 3: Update memory** — add/refresh a memory entry: *Phase 2 B0 outcome* (verified win + version OR honest no-win), perf-benchmark self-applied to the family, perf-smell narrowing deferred; B1–B4 still pending their own specs. Update `MEMORY.md` index line.
- [ ] **Step 4: STOP.** Do NOT begin B1–B4 — each gets its own spec.

---

## Self-Review (planner)

- **Spec coverage:** §2 success criteria → Tasks 4–5 (accept/no-win both terminal). §3 "one bounded win" → Task 2 selects exactly one; Task 3 runs exactly one sub-task; Task 5B forbids falling through. §4 methodology → Task 1 (attribution + perf-benchmark) and Task 4 (identical re-measure + verify_win). §5 candidates → Tasks 3-C1..C4, each fully written. §6 decision rule → Task 2 Step 2. §7 perf-smell defer → Task 7. §8 ship → Task 6 with all Phase-1 lessons (read-back, fresh-clone sim, fetch-depth:0, repo-P ruff, growth re-baseline, real-CI verify). §9 DoD → Task 9 Step 2. Stale-text correction → Task 8.
- **Placeholder scan:** no TBD/TODO; every code/command step shows actual content; the only intentional variable is the long-pole suite name (parameterised from Task 1 data, with `test-redundancy-triage` as the measured default).
- **Type/identity consistency:** `HEAVY` (run_checks), `suite_dirs`/`run_suite`/`XDIST_SUITES` (check_full_pytest), `suite_env`/`_run_one_suite`/`SUITES` (check_coverage_gap), `wall_time_percentiles.p50` + `verify_win.py` flags (`--before/--after/--suite-exit-code/--min-win/--ledger/--out`) all match the real source read on 2026-06-14.
- **Branchiness note:** this is a measure-then-decide plan; the conditional Task 3 sub-tasks and Task 5 verdict branch are intentional and each path is fully specified, so subagent execution stays unambiguous given the recorded decision.
