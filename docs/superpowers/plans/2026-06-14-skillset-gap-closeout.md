# Skillset Gap Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the bounded gaps found in the 2026-06-14 whole-skillset review — most importantly, enforce the convergence/acceptance gate in CI for repo-B and repo-P — plus a set of small, concrete cleanups across all three family repos. Each touched repo gets the standard ship cycle (commit/push/tag/release/reinstall).

**Architecture:** Independent, mostly per-repo fixes. The headline change adds a dedicated CI job to repo-B and repo-P that installs the leaf toolchain, clones the leaves (and the runner, for repo-P), and runs `check_wave_baseline.py` so the acceptance gate is CI-enforced. The rest are small, isolated edits (stale config/doc cleanup, two reference-quality fixes, one telemetry fix, one SKILL.md instruction fix). No new subsystems.

**Tech Stack:** Python 3.11+ stdlib + the pinned leaf toolchain (`lizard radon vulture ruff bandit pylint perflint mypy coverage` + `jscpd` via npm); pytest; GitHub Actions. Lessons honored: L1 (`npm ci` in fresh worktree), L2 (changelog date == commit date), L3 (fresh-clone/CI sim before declaring done), L4 (grep gate JSON, never a piped exit code).

**Source review:** the gaps this plan closes are enumerated in the 2026-06-14 review (see the acceptance-safeguard work in `docs/superpowers/{specs,plans}/2026-06-14-portable-acceptance-safeguard-*`).

---

## Scope

**In scope (this plan):** CI gate enforcement (repo-B, repo-P); stale `hotspot_audit_config.json` coupling pair (repo-B, repo-P); repo-P accept-validation test; push the MPRR remediation filter into `mprr_normalize`/`mprr_partition` + refresh the stale SP15 note (repo-B); inline example in `references/acceptance.md` (repo-B); `LM2` telemetry fix (repo-B); `instruction-eval/complexity-audit` SKILL.md fix (repo-A); merged-branch housekeeping; ship each touched repo.

**Out of scope — deferred to their own specs/plans (too large or research-driven for bite-sized tasks here):**
- **Self-application campaign** — point `test-redundancy-triage`, `test-effectiveness-audit`, `test-quality-assurance`, `perf-benchmark`, `perf-optimization` at the family. The first target (`test-redundancy-triage`) is entangled with the **300s bootstrap-probe timeout** investigation; that is a measurement+optimization effort needing its own brainstorm.
- **SP15 strategic backlog** — wiring non-redundancy lanes into the MPRR engine; across-repo fan-out; multi-language remediation; region/hunk conflict models; a tests-scoped dead-code gate; a duplicate-top-level-def detector; non-Python (JS/TS/C/Rust) leaves.

Each out-of-scope item is a standalone effort; opening them here would violate the single-plan scope rule.

---

## File Structure

- **repo-B** (`~/projects/repo-audit-refactor-optimize`):
  - Modify `scripts/hotspot_audit_config.json` (drop the deleted-file coupling pair), `scripts/mprr_normalize.py` + `scripts/mprr_partition.py` + `scripts/mprr_run.py` (push the remediation filter down), `references/acceptance.md` (inline example), `scripts/mine_iteration_kpis.py` (LM2), `docs/superpowers/SP15-CANDIDATES.md` lives in repo-A — see note in Task 4.
  - Create `.github/workflows/` convergence-gate job (extend `check.yml`).
  - Tests: extend `tests/test_mprr_run.py` / add `tests/test_mprr_partition.py`, extend `tests/test_mine_iteration_kpis.py`.
- **repo-P** (`~/projects/perf-benchmark-skill`): modify `scripts/hotspot_audit_config.json`; add `tests/test_accept_policy.py`; extend `.github/workflows/check.yml` with the gate job.
- **repo-A** (`~/projects/repo-audit-skills`): modify `skills/complexity-audit/SKILL.md`; update `docs/superpowers/SP15-CANDIDATES.md`.

**Baseline before starting (record):** all three repos on clean `main`, CI green, gates green (repo-B `check_wave_baseline` → `{"status":"pass","accepted":20,"active":0}`; repo-P → pass; repo-A `npm run check` 10/10+2/2). Create a branch per repo: `fix/gap-closeout`.

---

## Task 1 (repo-B + repo-P): remove the stale `wave_baseline.json` coupling pair

**Files:**
- Modify: `scripts/hotspot_audit_config.json` (repo-B and repo-P)

The deleted `scripts/wave_baseline.json` is still named in a `declared_coupling` pair in both configs — dead config pointing at a non-existent file.

- [ ] **Step 1: Inspect the config** — `cat scripts/hotspot_audit_config.json` in each repo. Find the `declared_coupling` entry containing `"scripts/wave_baseline.json"`. In repo-B it is paired with `scripts/wave_frozen.md`; the ratchet ledger pair is now `.repo-audit/accept.json <-> scripts/wave_frozen.md`. In repo-P it is the pair `["scripts/wave_baseline.json", "scripts/wave_frozen.md"]`.

- [ ] **Step 2: Edit** — replace `scripts/wave_baseline.json` with `.repo-audit/accept.json` in that coupling pair (the ratchet ledger relationship is preserved, now pointing at the live policy file). If the pair becomes meaningless, delete the pair entirely. Keep JSON valid.

- [ ] **Step 3: Verify the gate stays green** (repo-B):
```
WAVE_RUNNER="$(pwd)/scripts/run_diagnosis_wave.py" SKILLS_ROOT=~/.claude/skills python3 scripts/check_wave_baseline.py
```
Expected: `{"status":"pass","accepted":20,"active":0}`. (repo-P: `python3 scripts/check_wave_baseline.py` → pass, active 0.) If a NEW hotspot coupling finding appears from the edit, it is real churn on the config file — accept it in that repo's `.repo-audit/accept.json` with a one-line reason, or revert if it indicates the pair was load-bearing.

- [ ] **Step 4: Commit** (in each repo):
```bash
git add scripts/hotspot_audit_config.json
git commit -m "fix(hotspot): drop declared-coupling pair for the removed wave_baseline.json"
```

---

## Task 2 (repo-P): test that the repo's own `.repo-audit/accept.json` is valid

**Files:**
- Create: `tests/test_accept_policy.py`

repo-P has no `_accept.py` and no test guarding its own acceptance policy (repo-B has `test_baseline_ledger.py`; repo-A is covered by `npm run check`). Add a self-contained validator test.

- [ ] **Step 1: Write the test** — create `tests/test_accept_policy.py`:

```python
"""Guard repo-P's own .repo-audit/accept.json: well-formed, every entry justified."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ACCEPT = REPO / ".repo-audit" / "accept.json"
_STAGES = {"report", "remediation"}
_KINDS = {"finding", "path", "rule"}


def _entries() -> list[dict]:
    data = json.loads(ACCEPT.read_text(encoding="utf-8"))
    assert data.get("version") == 1, "accept policy version must be 1"
    accept = data.get("accept")
    assert isinstance(accept, list) and accept, "accept must be a non-empty array"
    return accept


def test_accept_file_exists():
    assert ACCEPT.is_file(), f"missing {ACCEPT}"


def test_every_entry_is_well_formed_and_justified():
    for i, e in enumerate(_entries()):
        match = e.get("match")
        assert isinstance(match, dict), f"accept[{i}].match missing"
        assert match.get("kind") in _KINDS, f"accept[{i}].kind invalid"
        assert isinstance(e.get("reason"), str) and e["reason"].strip(), f"accept[{i}] reason required"
        applies = e.get("applies", ["report", "remediation"])
        assert applies and set(applies) <= _STAGES, f"accept[{i}].applies invalid"
        if match["kind"] == "finding":
            assert all(k in match for k in ("leaf", "path", "symbol", "metric")), f"accept[{i}] finding incomplete"
        elif match["kind"] == "path":
            assert isinstance(match.get("glob"), str) and ".." not in match["glob"], f"accept[{i}] path glob invalid"
        else:
            assert "leaf" in match or "metric" in match, f"accept[{i}] rule needs leaf/metric"
```

- [ ] **Step 2: Run to verify it passes** (the file is already valid):

Run: `python3 -m pytest tests/test_accept_policy.py -q`
Expected: PASS (3 tests). If it fails, the committed `.repo-audit/accept.json` is malformed — fix the file, not the test.

- [ ] **Step 3: Negative-test it once by hand** — temporarily blank a `reason` in a scratch copy and confirm the assertion fires, then discard the scratch change (do not commit it). This proves the guard bites.

- [ ] **Step 4: Commit:**
```bash
git add tests/test_accept_policy.py
git commit -m "test(accept): guard repo-P's .repo-audit/accept.json (well-formed + justified)"
```

---

## Task 3 (repo-B): push the remediation filter into `mprr_normalize`/`mprr_partition`

**Files:**
- Modify: `scripts/mprr_partition.py` (add a stage-aware filter helper)
- Modify: `scripts/mprr_run.py` (`_cmd_plan` calls the shared helper)
- Test: `tests/test_mprr_partition.py` (create)

Today `_cmd_plan` filters remediation-accepted findings via `_filter_remediation` before `normalize`. The SP15 residual: a direct caller of `mprr_normalize.normalize()` bypasses the filter. Make the filter a reusable function in `mprr_partition.py` (the conflict/eligibility module) and route `_cmd_plan` through it, so the engine layer owns the policy.

- [ ] **Step 1: Write the failing test** — create `tests/test_mprr_partition.py`:

```python
import importlib
import json
from pathlib import Path

part = importlib.import_module("scripts.mprr_partition")


def test_filter_accepted_drops_remediation_matches(tmp_path: Path):
    (tmp_path / ".repo-audit").mkdir()
    (tmp_path / ".repo-audit" / "accept.json").write_text(json.dumps(
        {"version": 1, "accept": [
            {"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "intentional"}]}),
        encoding="utf-8")
    findings = [{"id": "a", "files": ["src/x.py"]},
                {"id": "b", "files": ["tests/fixtures/y.py"]}]
    kept, excluded = part.filter_accepted(findings, tmp_path)
    assert [f["id"] for f in kept] == ["a"]
    assert excluded[0]["id"] == "b" and excluded[0]["accept_reason"] == "intentional"


def test_filter_accepted_noop_without_policy(tmp_path: Path):
    findings = [{"id": "a", "files": ["src/x.py"]}]
    kept, excluded = part.filter_accepted(findings, tmp_path)
    assert kept == findings and excluded == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_mprr_partition.py -q`
Expected: FAIL — `filter_accepted` undefined.

- [ ] **Step 3: Implement** — add to `scripts/mprr_partition.py` (it currently imports only `Iterable`; add the `_accept` import the import-robust way the sibling modules use, and `Path`/`json`):

```python
import importlib
import json
from pathlib import Path

_accept = importlib.import_module("scripts._accept" if __package__ else "_accept")


def _engine_policy(repo: Path):
    """Target-repo acceptance policy + legacy remediation_excludes.json fallback."""
    policy = _accept.load_accept(repo)
    legacy = Path(repo) / "scripts" / "remediation_excludes.json"
    if legacy.exists():
        data = json.loads(legacy.read_text())
        entries = []
        for section in data.values():
            if not isinstance(section, dict):
                continue
            reason = section.get("reason", "(remediation_excludes.json)")
            for glob in section.get("exclude_paths", []):
                entries.append(_accept.AcceptEntry(
                    "path", {"glob": glob}, reason, frozenset({"remediation"}), None))
        policy = policy.merge(_accept.AcceptPolicy(entries))
    return policy


def filter_accepted(findings, repo):
    """Drop findings accepted at the remediation stage. Returns (kept, excluded)."""
    policy = _engine_policy(Path(repo))
    if not policy.entries:
        return findings, []
    kept, excluded, _stale = policy.partition(findings, "remediation")
    return kept, excluded
```

- [ ] **Step 4: Route `_cmd_plan` through it** — in `scripts/mprr_run.py`, replace the `_engine_accept_policy`/`_filter_remediation` usage inside `_cmd_plan` with `mprr_partition.filter_accepted`, writing the sidecar from the returned `excluded`:

```python
    raw_findings = _load(a.findings)
    if a.repo:
        raw_findings, excluded = mprr_partition.filter_accepted(raw_findings, a.repo)
        if excluded:
            (run_dir / "mprr_excluded.json").write_text(
                json.dumps({"excluded": excluded}, indent=2), encoding="utf-8")
    items = mprr_normalize.normalize(raw_findings)
```

Remove the now-duplicated `_engine_accept_policy`/`_filter_remediation` from `mprr_run.py` (the logic now lives in `mprr_partition`). Keep `mprr_run`'s existing `_accept` import only if still used elsewhere; otherwise drop it. Update `tests/test_mprr_run.py`'s two Phase-1 tests to call `mprr_partition.filter_accepted` (or assert via `_cmd_plan` end-to-end), since `_engine_accept_policy`/`_filter_remediation` moved.

- [ ] **Step 5: Run the MPRR suites**

Run: `python3 -m pytest tests/test_mprr_partition.py tests/test_mprr_run.py -q`
Expected: PASS. Then full suite `python3 -m pytest tests/ -q` stays green.

- [ ] **Step 6: Commit:**
```bash
git add scripts/mprr_partition.py scripts/mprr_run.py tests/test_mprr_partition.py tests/test_mprr_run.py
git commit -m "refactor(mprr): own the remediation accept-filter in mprr_partition (engine self-filters; closes SP15 residual)"
```

---

## Task 4 (repo-A): refresh the stale SP15 candidate note

**Files:**
- Modify: `docs/superpowers/SP15-CANDIDATES.md` (in repo-A)

The "Auto-consume the remediation-scope policy in the engine" candidate is now resolved (Phase 1 wired `mprr_run` to load `.repo-audit/accept.json`; Task 3 pushes it into `mprr_partition`). The doc still says the engine "still does not load it."

- [ ] **Step 1: Edit** — in repo-A `docs/superpowers/SP15-CANDIDATES.md`, mark that candidate **RESOLVED**: "Phase 2 folded the policy into `.repo-audit/accept.json`; the MPRR engine now loads it (`mprr_run` → `mprr_partition.filter_accepted`), so intentional residue is never proposed." Keep the historical text struck-through or annotated, matching the doc's existing resolved-item style (the growth-audit item shows the `~~strikethrough~~ **RESOLVED**` pattern).

- [ ] **Step 2: Commit** (this is part of repo-A's branch; see Task 8 for repo-A grouping):
```bash
git add docs/superpowers/SP15-CANDIDATES.md
git commit -m "docs(sp15): mark engine-auto-consume candidate resolved (Phase 2 + mprr_partition)"
```

---

## Task 5 (repo-B): inline example in `references/acceptance.md`

**Files:**
- Modify: `references/acceptance.md`

- [ ] **Step 1: Edit** — replace the `## Example` pointer line ("See the three-entry example in the design spec.") with an inline example so the authoring guide is self-contained:

```markdown
## Example

​```json
{
  "version": 1,
  "accept": [
    {"match": {"kind": "finding", "leaf": "complexity", "path": "scripts/x.py",
               "symbol": "<module>", "metric": "maintainability_index"},
     "reason": "Cohesive single-file tool; splitting to chase MI relocates, not reduces.",
     "applies": ["report"]},
    {"match": {"kind": "path", "glob": "**/tests/fixtures/**"},
     "reason": "Detection-coupled fixtures must stay dirty.", "applies": ["remediation"]},
    {"match": {"kind": "rule", "leaf": "growth-audit"},
     "reason": "Skill repo grows with features; growth deltas are expected.",
     "applies": ["report"], "expires": "v1.0.0"}
  ]
}
​```
```
(Drop the leading zero-width characters around the code fences — they are only shown here to keep the fence from closing this plan's block.)

- [ ] **Step 2: Verify docs gate stays clean** — the example references repo-relative paths only; no out-of-scope slash-path tokens that the docs-consistency leaf would flag. Re-run the repo-B gate (Task 1 Step 3) → still pass.

- [ ] **Step 3: Commit:**
```bash
git add references/acceptance.md
git commit -m "docs(accept): inline the example in references/acceptance.md (self-contained guide)"
```

---

## Task 6 (repo-B): fix LM2 — allocator surplus yield always 0

**Files:**
- Modify: `scripts/mine_iteration_kpis.py`
- Test: `tests/test_mine_iteration_kpis.py`

`LM2` (lessons.jsonl): `allocate_batches` derives per-repo trailing yield from `rows_before`/`rows_after`, but `mine_iteration_kpis` emits a scalar `rows_closed` without per-repo `rows_before`/`rows_after` dicts, so the allocator's yield is always 0 and surplus falls back to first-active. Fix: have the miner emit per-repo `rows_before`/`rows_after` alongside `rows_closed`.

- [ ] **Step 1: Read the current emission** — `grep -nE "rows_closed|rows_before|rows_after|def _emit|json.dump|def main" scripts/mine_iteration_kpis.py`. Identify where the KPI dict is assembled in `main` (it already computes `rows_before`/`rows_after` dicts locally via `_load_baseline_rows` at the start/end SHAs — see the `rows_before = _load_baseline_rows(...)` / `rows_after = _load_baseline_rows(...)` calls).

- [ ] **Step 2: Write the failing test** — append to `tests/test_mine_iteration_kpis.py`:

```python
def test_kpis_emit_per_repo_rows_before_and_after(tmp_path, monkeypatch, capsys):
    # Build the KPI payload via main() over a tiny repo with a baseline that grows.
    import importlib, json
    kpi = importlib.import_module("scripts.mine_iteration_kpis")
    payload = kpi.build_kpis(  # see Step 3 for this seam
        rows_before={"accept": 19}, rows_after={"accept": 20},
        worker_runs=[], phase_seconds={}, ci_wait_seconds=0,
    )
    assert payload["rows_before"] == {"accept": 19}
    assert payload["rows_after"] == {"accept": 20}
    assert payload["rows_closed"] == 0 or "rows_closed" in payload  # scalar still present
```

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -k per_repo_rows -q`
Expected: FAIL — either `build_kpis` does not exist as a seam, or the payload lacks `rows_before`/`rows_after`.

- [ ] **Step 4: Implement** — extract the payload assembly in `main` into a `build_kpis(rows_before, rows_after, worker_runs, phase_seconds, ci_wait_seconds, **rest)` helper (pure, testable) that includes the per-repo `rows_before` and `rows_after` dicts in the emitted KPI object (in addition to the existing scalar `rows_closed`). `main` computes `rows_before`/`rows_after` via `_load_baseline_rows` and passes them in. Keep the existing scalar `rows_closed` for back-compat. Example shape added to the payload:

```python
    payload = {
        # ... existing keys ...
        "rows_before": rows_before,   # {baseline_key: count} per the loaded baseline
        "rows_after": rows_after,
        "rows_closed": _rows_closed(rows_before, rows_after),  # existing scalar
    }
```

- [ ] **Step 5: Run to verify it passes**

Run: `python3 -m pytest tests/test_mine_iteration_kpis.py -q`
Expected: PASS (existing tests + the new one). The allocator (`scripts/allocate_batches.py`) can now read `rows_before`/`rows_after`; no allocator change is required for this fix (it already looks for those keys per LM2). If an allocator test exercises yield, confirm it now sees non-zero yield when rows close.

- [ ] **Step 6: Mark the lesson resolved** — in repo-A `docs/self-audit/lessons.jsonl`, set `LM2`'s `"escalated": true` with an `"escalation"` note pointing at this commit (mirror how `LM1` was marked). (This edit lands in repo-A's branch — group with Task 8.)

- [ ] **Step 7: Commit** (repo-B):
```bash
git add scripts/mine_iteration_kpis.py tests/test_mine_iteration_kpis.py
git commit -m "fix(kpis): emit per-repo rows_before/rows_after so allocator surplus yield is real (LM2)"
```

---

## Task 7 (repo-A): fix `instruction-eval/complexity-audit` — module-MI under-specification

**Files:**
- Modify: `skills/complexity-audit/SKILL.md` (in repo-A)
- Verify: repo-B `scripts/run_instruction_eval.py` against the updated SKILL.md

The candidate lesson: a pinned model given only `complexity-audit`'s SKILL.md produced 1 finding row vs 2 expected — it missed the module-level `maintainability_index` SIMPLIFY finding and conflated SIMPLIFY vs DECOMPOSE. Fix the SKILL.md so the two finding classes are unambiguous.

- [ ] **Step 1: Read the current SKILL.md** — `cat skills/complexity-audit/SKILL.md`. Locate the section describing findings / SIMPLIFY vs DECOMPOSE and the metrics (cyclomatic_complexity, function_nloc, parameter_count, maintainability_index).

- [ ] **Step 2: Edit for clarity** — make explicit that the leaf emits **two distinct finding kinds**: (a) per-function `DECOMPOSE` findings for `cyclomatic_complexity` / `function_nloc` / `parameter_count` over threshold; and (b) a **per-module `SIMPLIFY` finding for `maintainability_index`** below the `mi_low` threshold (symbol `<module>`). Add a one-line worked example showing a module that emits BOTH a function-level DECOMPOSE and a module-level SIMPLIFY row, so a reader cannot conflate them. Keep within the leaf's existing SKILL.md length budget (no contract changes — wording only).

- [ ] **Step 3: Re-run the instruction eval** — from repo-B:
```
python3 scripts/run_instruction_eval.py --skill ~/.claude/skills/complexity-audit/SKILL.md  # confirm the actual flags via --help first
```
Compare to the recorded `docs/self-audit/eval_complexity-audit.json` (in repo-A). Expected: the eval now yields the expected 2 rows (module-MI SIMPLIFY + the function DECOMPOSE), not 1. If the harness needs the updated SKILL.md installed first, reinstall complexity-audit (`node bin/install-repo-audit-skills.js --dest ~/.claude/skills --force` from repo-A) before re-running. Record the new eval JSON.

- [ ] **Step 4: Mark the candidate resolved** — update repo-A `docs/self-audit/lessons.jsonl` `instruction-eval/complexity-audit` entry with the new eval result + `"escalated": true`.

- [ ] **Step 5: Commit** (repo-A):
```bash
git add skills/complexity-audit/SKILL.md docs/self-audit/eval_complexity-audit.json docs/self-audit/lessons.jsonl
git commit -m "docs(complexity-audit): disambiguate module-MI SIMPLIFY vs function DECOMPOSE (instruction-eval fix)"
```

---

## Task 8 (repo-B + repo-P): wire the convergence gate into CI

**Files:**
- Modify: `.github/workflows/check.yml` (repo-B and repo-P)

This is the headline fix: enforce the acceptance/convergence gate in CI for the two wave-based repos. Add a **separate job** that installs the leaf toolchain, clones the leaves (and the runner, for repo-P), and runs `check_wave_baseline.py`.

- [ ] **Step 1 (repo-B): add the `convergence-gate` job** to `.github/workflows/check.yml`:

```yaml
  convergence-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v6
        with:
          node-version: '22'
      - uses: actions/setup-python@v6
        with:
          python-version: '3.12'
      - name: Install leaf toolchain
        run: |
          python -m pip install --upgrade pip
          python -m pip install \
            coverage==7.14.1 pytest==9.0.3 pytest-cov==7.1.0 \
            lizard==1.23.0 radon==6.0.1 vulture==2.16 ruff==0.15.16 \
            mypy==2.1.0 bandit==1.9.4 mutmut==3.6.0 pylint==3.3.9 \
            astroid==3.3.11 perflint==0.8.1
      - name: Clone leaves (repo-audit-skills)
        run: |
          git clone --depth 1 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves
          (cd /tmp/leaves && npm install)   # jscpd for the duplication leaf
      - name: Run convergence gate
        run: |
          WAVE_RUNNER="$GITHUB_WORKSPACE/scripts/run_diagnosis_wave.py" \
          SKILLS_ROOT=/tmp/leaves/skills \
          python3 scripts/check_wave_baseline.py | tee /tmp/gate.json
          python3 - <<'PY'
          import json,sys
          # grep the verdict JSON (last object); fail on non-pass (lesson L4)
          text=open("/tmp/gate.json").read()
          obj=json.loads(text[text.rstrip().rfind("{\n"):])
          print("gate:", obj.get("status"), "active:", obj.get("active"))
          sys.exit(0 if obj.get("status")=="pass" else 1)
          PY
```

- [ ] **Step 2 (repo-P): add the same job** to repo-P `.github/workflows/check.yml`, but clone BOTH the leaves AND the runner, and point `WAVE_RUNNER` at the cloned runner:

```yaml
  convergence-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v6
        with: { node-version: '22' }
      - uses: actions/setup-python@v6
        with: { python-version: '3.12' }
      - name: Install leaf toolchain
        run: |
          python -m pip install --upgrade pip
          python -m pip install coverage==7.14.1 pytest==9.0.3 pytest-cov==7.1.0 \
            lizard==1.23.0 radon==6.0.1 vulture==2.16 ruff==0.15.16 mypy==2.1.0 \
            bandit==1.9.4 mutmut==3.6.0 pylint==3.3.9 astroid==3.3.11 perflint==0.8.1
      - name: Clone leaves + runner
        run: |
          git clone --depth 1 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves
          (cd /tmp/leaves && npm install)
          git clone --depth 1 https://github.com/jc1122/repo-audit-refactor-optimize.git /tmp/runner
      - name: Run convergence gate
        run: |
          WAVE_RUNNER=/tmp/runner/scripts/run_diagnosis_wave.py \
          SKILLS_ROOT=/tmp/leaves/skills \
          python3 scripts/check_wave_baseline.py | tee /tmp/gate.json
          python3 - <<'PY'
          import json,sys
          text=open("/tmp/gate.json").read()
          obj=json.loads(text[text.rstrip().rfind("{\n"):])
          print("gate:", obj.get("status"), "active:", obj.get("active"))
          sys.exit(0 if obj.get("status")=="pass" else 1)
          PY
```

- [ ] **Step 3: Local CI sim** (lesson L3 — prove the job before pushing). In a scratch dir, reproduce the job steps for each repo: fresh `git clone` the leaves to `/tmp/leaves` (+ runner for repo-P), `npm install` in the leaves clone, then run the gate command exactly as the YAML does. Confirm it prints `gate: pass active: 0` and exits 0. (The leaf toolchain is already installed locally from this session.)

- [ ] **Step 4: Commit** (each repo):
```bash
git add .github/workflows/check.yml
git commit -m "ci: enforce the convergence/acceptance gate (clone leaves + run check_wave_baseline)"
```

> **Note:** the gate clones leaves from `main`. That is intentional (the gate should track the current leaf behavior). If a pinned-leaf gate is later wanted, clone a tag instead. The gate job runs in parallel with the existing `check` job, so it does not slow the primary signal.

---

## Task 9 (all repos): merged-branch housekeeping + ship

**Files:** none (git + release)

- [ ] **Step 1: Delete merged local feature branches** (they are already merged to `main`):
```bash
git -C ~/projects/repo-audit-refactor-optimize branch -d feat/acceptance-safeguard
git -C ~/projects/repo-audit-skills branch -d chore/accept-migration
git -C ~/projects/perf-benchmark-skill branch -d chore/reanchor-accept-migration
```
(Use `-d`, not `-D`, so git refuses if anything is unmerged.)

- [ ] **Step 2: Ship each touched repo** — for repo-B, repo-P, repo-A in turn: merge `fix/gap-closeout` → `main` (`--no-ff`), bump the version + dated CHANGELOG entry (repo-B `0.8.0→0.8.1`; repo-P `0.4.1→0.4.2`, heading `## 0.4.2 - 2026-06-14`; repo-A family `0.7.1→0.7.2` synced via `check_release.py`), run the full local gate set (repo-B: `pytest` + `check_release` + `check_wave_baseline`; repo-P: `ruff` + `pytest` + `check_wave_baseline`; repo-A: `npm run check`), fresh-clone/CI sim (L3), push `main` + tag + `gh release`, reinstall (repo-B/P rsync to `~/.claude/skills`; repo-A `node bin/install-repo-audit-skills.js --dest ~/.claude/skills --force`).

- [ ] **Step 3: Purge any transient growth allowances** that the repo-A version bump trips, after tagging (the established `149a1e5` pattern): reset `scripts/growth_allowances.json` to only the `dependency_growth` entry, confirm `python3 scripts/check_growth.py` → `{"status":"pass","count":0,"baseline":"v0.7.2"}`, commit `chore(gates): purge growth allowances at v0.7.2`, push.

- [ ] **Step 4: Verify CI green** on every pushed commit for all three repos (`gh run list --branch main --limit 2` per repo → `success`, including the new `convergence-gate` job). If the new gate job is red, read `gh run view <id> --log-failed` and fix before declaring done (do not leave a red gate).

---

## Final verification

- [ ] All three repos: clean `main`, CI green **including the new convergence-gate job** (repo-B/P) and `npm run check` (repo-A).
- [ ] repo-B `check_wave_baseline` → `{"status":"pass","accepted":20,"active":0}`; repo-P → pass active 0; repo-A `npm run check` 10/10+2/2.
- [ ] `git grep wave_baseline.json` in repo-B/P returns only synthetic test fixtures + historical `docs/` / CHANGELOG entries (no live config).
- [ ] repo-P `tests/test_accept_policy.py` green; repo-B `tests/test_mprr_partition.py` + `tests/test_mine_iteration_kpis.py` green.
- [ ] Installed versions: repo-B 0.8.1, perf-benchmark 0.4.2, repo-A family 0.7.2.
- [ ] Memory updated: note the gap closeout + that the gate is now CI-enforced for all three repos.

---

## Self-Review (completed by planner)

- **Coverage of in-scope gaps:** CI enforcement → Task 8; stale hotspot config → Task 1; repo-P accept test → Task 2; mprr push-down + stale SP15 doc → Tasks 3+4; acceptance.md example → Task 5; LM2 → Task 6; instruction-eval/complexity-audit → Task 7; branch housekeeping + ship → Task 9. Every in-scope review item maps to a task. Out-of-scope (self-application campaign, SP15 strategic) explicitly deferred with rationale.
- **Placeholder scan:** no TBD/TODO; code/YAML shown in full. Two tasks (7 module-MI eval, 8 gate job) end in a *measured* verification (eval row count / CI green) rather than a fixed literal because their pass condition is environmental — each names the exact command and expected outcome, not a vague "verify".
- **Type/identity consistency:** `filter_accepted(findings, repo) -> (kept, excluded)` (Task 3) matches its `_cmd_plan` call site and test; `_engine_policy` mirrors the retired `_engine_accept_policy`. `build_kpis(rows_before, rows_after, ...)` (Task 6) matches its test and `main` wiring. The CI gate command matches the working local invocation (`WAVE_RUNNER`/`SKILLS_ROOT` + `check_wave_baseline.py`) proven this session.
- **Cross-repo edits flagged:** Tasks 4, 6-Step-6, and 7 touch repo-A; they are grouped onto repo-A's `fix/gap-closeout` branch in Task 9-Step-2. Tasks 1 and 8 touch both repo-B and repo-P (same edit in each).
- **Risk:** lowest-risk first (config/doc/test), highest-value (CI gate) before ship; every gate re-verified after each change; L1-L4 honored in Task 8/9.
