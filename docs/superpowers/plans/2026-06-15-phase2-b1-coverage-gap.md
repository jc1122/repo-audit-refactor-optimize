# Phase 2 · B1 — coverage-gap testedness convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the `coverage-gap` advisory lane against all three family repos and converge each to **zero** findings — verifying repo-A (already 0), and **closing** the one genuine gap in repo-B (`run_instruction_eval.py` 33.3 %) and the one in repo-P (`findings.py` 47.5 %) with added behaviour tests — then commit a reproducible coverage recipe + evidence. No accept entries, no release.

**Architecture:** Measure-then-converge. repo-A is verify-only (its `check_coverage_gap.py` gate already enforces coverage-gap at `_prefixes()` scope, baseline `[]`). repo-B and repo-P each get a TDD test-closure of one pure stdlib module, lifting it well above the leaf's 50 % `min_file_coverage` threshold. Coverage is generated with **subprocess capture** (sitecustomize hook + `COVERAGE_PROCESS_START` + `parallel`+`combine`) so subprocess-tested CLIs are not falsely reported as 0 %. Closing (not accepting) avoids the wave-gate stale-acceptance landmine entirely.

**Tech Stack:** Python 3.14, pytest, coverage.py 7.14.1, the `coverage-gap-audit` leaf (`~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py`), git + `gh`.

**Spec:** `docs/superpowers/specs/2026-06-15-phase2-b1-coverage-gap-design.md`

---

## Repo / path conventions

- **repo-A** = `/home/jakub/projects/repo-audit-skills` (leaves; coverage-gap already gated)
- **repo-B** = `/home/jakub/projects/repo-audit-refactor-optimize` (campaign home; spec/plan/evidence live here)
- **repo-P** = `/home/jakub/projects/perf-benchmark-skill` (perf-benchmark + perf-optimization)
- **LEAF** = `python3 ~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py`
- Scratch (gitignored, NOT committed): `/tmp/b1/`
- Committed evidence (repo-B): `docs/superpowers/b1-evidence/`
- Subprocess-coverage hook (scratch): `/tmp/b1/cov-hook/sitecustomize.py` = `import coverage\ncoverage.process_startup()`

---

## File Structure

| File | Repo | Responsibility | Task |
|------|------|----------------|------|
| `tests/test_run_instruction_eval.py` | B | extend with CLI/IO behaviour tests (`_load_expected`, `_load_model_findings`, `_build_parser`, `main`) | Task 2 |
| `tests/test_findings_bridge.py` | P | extend with inference-handler tests (`_extract_*`, `_build_finding` severity, `_suggested_action`) | Task 3 |
| `docs/superpowers/b1-evidence/recipe.md` | B | reproducible coverage-generation recipe per repo | Task 4 |
| `docs/superpowers/b1-evidence/before-after.md` | B | per-repo finding inventory before/after | Task 4 |
| `docs/superpowers/b1-evidence/*-findings-*.json` | B | leaf finding artifacts (before/after) | Tasks 1,4 |

No production source changes. No `.repo-audit/accept.json` changes. No `SKILL.md`/version/CHANGELOG changes.

---

## Task 0: Branch setup + green baselines

**Files:** none (git + verification only)

- [ ] **Step 1: Confirm repo-B branch** (created during brainstorming)

Run: `cd /home/jakub/projects/repo-audit-refactor-optimize && git branch --show-current`
Expected: `feat/phase2-b1`. If not: `git checkout feat/phase2-b1`.

- [ ] **Step 2: Create repo-B and repo-P work branches from clean main**

```bash
cd /home/jakub/projects/perf-benchmark-skill && git checkout main && git checkout -b feat/phase2-b1 && git branch --show-current
```
Expected: clean tree, `feat/phase2-b1`. (repo-B already on its branch from Step 1; repo-A gets NO branch — verify-only.)

- [ ] **Step 3: Confirm both suites GREEN before changing anything**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/ -q -p no:cacheprovider | tail -2
cd /home/jakub/projects/perf-benchmark-skill && python3 -m pytest tests/ perf-optimization/tests/ -q -p no:cacheprovider | tail -2
```
Expected: both report all-passed (repo-B ~290, repo-P ~166). If RED, STOP and triage (do not converge a broken tree).

- [ ] **Step 4: Create scratch + evidence dirs and the subprocess hook**

```bash
mkdir -p /tmp/b1/cov-hook /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b1-evidence
printf 'import coverage\ncoverage.process_startup()\n' > /tmp/b1/cov-hook/sitecustomize.py
```

---

## Task 1: repo-A verification (verify-only, no change)

**Files:** Create `docs/superpowers/b1-evidence/repoA-findings.json` (repo-B)

- [ ] **Step 1: Run repo-A's real coverage-gap gate against its committed coverage artifact**

```bash
cd /home/jakub/projects/repo-audit-skills && python3 scripts/check_coverage_gap.py \
  --coverage-json .self_audit_out/coverage/coverage.json
```
Expected: `{"status": "pass", "count": 0, "baseline": 0, ...}`. This proves repo-A's coverage-gap lane already runs and converges at 0. (If `.self_audit_out/coverage/coverage.json` is missing, regenerate it with `npm run check` first.)

- [ ] **Step 2: Capture the leaf finding artifact at the gate's exact scope for evidence**

```bash
cd /home/jakub/projects/repo-audit-skills && python3 ~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  --root "$(pwd)" --source-prefix shared --source-prefix scripts \
  $(for d in skills/*/scripts; do echo --source-prefix "$d"; done) \
  --coverage-json .self_audit_out/coverage/coverage.json \
  --out-dir /tmp/b1/repoA-leaf
python3 -c "import json; d=json.load(open('/tmp/b1/repoA-leaf/coverage-gap_findings.json')); print('repo-A findings:', len(d)); assert len(d)==0, d"
cp /tmp/b1/repoA-leaf/coverage-gap_findings.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b1-evidence/repoA-findings.json
```
Expected: `repo-A findings: 0`; file copied. **Note:** the prefix list MUST be `shared`, `scripts`, and each `skills/*/scripts` — exactly `check_coverage_gap._prefixes()`. A bare `--source-prefix skills` sweeps in `tests/` and produces 183 false findings.

---

## Task 2: repo-B — close the `run_instruction_eval.py` gap (TDD)

**Files:** Modify `tests/test_run_instruction_eval.py` (repo-B, on `feat/phase2-b1`)

Target module `scripts/run_instruction_eval.py` is pure/deterministic/stdlib-only (it does NOT call an LLM). Existing tests cover `score_eval` + `advisory_outputs`. Add coverage for `_load_expected`, `_load_model_findings`, `_build_parser`, and `main`.

- [ ] **Step 1: Append the failing behaviour tests** to `tests/test_run_instruction_eval.py`:

```python
import json
import pytest


# --- _load_expected: int literal, JSON-int, JSON-dict, and error branches ---
def test_load_expected_int_literal():
    assert ev._load_expected("3") == 3


def test_load_expected_json_bare_int(tmp_path):
    p = tmp_path / "exp.json"
    p.write_text("7", encoding="utf-8")
    assert ev._load_expected(str(p)) == 7


def test_load_expected_json_dict(tmp_path):
    p = tmp_path / "exp.json"
    p.write_text(json.dumps({"expected_rows": 5}), encoding="utf-8")
    assert ev._load_expected(str(p)) == 5


def test_load_expected_missing_file_raises():
    with pytest.raises(ValueError):
        ev._load_expected("/no/such/file.json")


def test_load_expected_bool_json_raises(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("true", encoding="utf-8")
    with pytest.raises(ValueError):
        ev._load_expected(str(p))


def test_load_expected_bad_dict_raises(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"nope": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        ev._load_expected(str(p))


# --- _load_model_findings: valid array, missing, non-array ---
def test_load_model_findings_valid(tmp_path):
    p = tmp_path / "mf.json"
    p.write_text(json.dumps([{"a": 1}, {"b": 2}]), encoding="utf-8")
    assert ev._load_model_findings(str(p)) == [{"a": 1}, {"b": 2}]


def test_load_model_findings_missing_raises():
    with pytest.raises(ValueError):
        ev._load_model_findings("/no/such.json")


def test_load_model_findings_non_array_raises(tmp_path):
    p = tmp_path / "mf.json"
    p.write_text(json.dumps({"not": "array"}), encoding="utf-8")
    with pytest.raises(ValueError):
        ev._load_model_findings(str(p))


# --- _build_parser ---
def test_build_parser_parses_required_args_with_default_model():
    parser = ev._build_parser()
    ns = parser.parse_args(
        ["--skill", "complexity-audit", "--expected", "3", "--model-findings", "mf.json"]
    )
    assert ns.skill == "complexity-audit"
    assert ns.expected == "3"
    assert ns.model_findings == "mf.json"
    assert ns.model == "claude-opus-4-8"


# --- main: pass, drift, two error paths, default out path ---
def test_main_pass_writes_artifact_and_returns_zero(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([{"x": 1}, {"x": 2}, {"x": 3}]), encoding="utf-8")
    out = tmp_path / "eval.json"
    rc = ev.main(
        ["--skill", "complexity-audit", "--expected", "3",
         "--model-findings", str(mf), "--out", str(out)]
    )
    assert rc == 0
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["pass"] is True
    assert artifact["advisory"]["finding"] is None


def test_main_drift_writes_advisory_finding(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([{"x": i} for i in range(5)]), encoding="utf-8")
    out = tmp_path / "eval.json"
    rc = ev.main(
        ["--skill", "complexity-audit", "--expected", "3",
         "--model-findings", str(mf), "--out", str(out)]
    )
    assert rc == 0
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["pass"] is False
    assert artifact["advisory"]["finding"]["signal"] == "EVAL"


def test_main_malformed_model_findings_returns_two(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps({"not": "array"}), encoding="utf-8")
    rc = ev.main(
        ["--skill", "x", "--expected", "1", "--model-findings", str(mf),
         "--out", str(tmp_path / "o.json")]
    )
    assert rc == 2


def test_main_malformed_expected_returns_two(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([1]), encoding="utf-8")
    rc = ev.main(
        ["--skill", "x", "--expected", "/no/such.json",
         "--model-findings", str(mf), "--out", str(tmp_path / "o.json")]
    )
    assert rc == 2


def test_main_default_out_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    rc = ev.main(["--skill", "complexity-audit", "--expected", "3", "--model-findings", str(mf)])
    assert rc == 0
    assert (tmp_path / "eval_complexity-audit.json").is_file()
```

- [ ] **Step 2: Run the new tests — expect PASS** (the module already exists; these exercise untested paths):

Run: `cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/test_run_instruction_eval.py -q -p no:cacheprovider`
Expected: all PASS (old 3 + new 16). If any FAIL, the test encodes a wrong expectation — fix the test to match the module's real behaviour (do NOT change the module).

- [ ] **Step 3: Verify the gap is closed (coverage > 50 %, target ≥ 80 %)**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
rm -rf /tmp/b1/repoB && mkdir -p /tmp/b1/repoB
cat > /tmp/b1/repoB/.coveragerc <<'RC'
[run]
parallel = true
data_file = /tmp/b1/repoB/.coverage
[report]
ignore_errors = true
RC
PYTHONPATH=/tmp/b1/cov-hook:$PYTHONPATH COVERAGE_PROCESS_START=/tmp/b1/repoB/.coveragerc \
  python3 -m coverage run --rcfile=/tmp/b1/repoB/.coveragerc -m pytest tests/ -q -p no:cacheprovider >/tmp/b1/repoB/pytest.log 2>&1
echo "suite rc=$?"; tail -1 /tmp/b1/repoB/pytest.log
python3 -m coverage combine --rcfile=/tmp/b1/repoB/.coveragerc
python3 -m coverage json --rcfile=/tmp/b1/repoB/.coveragerc --data-file=/tmp/b1/repoB/.coverage -o /tmp/b1/repoB/coverage.json
python3 ~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  --root "$(pwd)" --source-prefix scripts --coverage-json /tmp/b1/repoB/coverage.json --out-dir /tmp/b1/repoB/leaf
python3 -c "import json; d=json.load(open('/tmp/b1/repoB/coverage.json'))['files']['scripts/run_instruction_eval.py']['summary']; print('run_instruction_eval coverage:', round(d['percent_covered'],1),'%')"
python3 -c "import json; d=json.load(open('/tmp/b1/repoB/leaf/coverage-gap_findings.json')); print('repo-B coverage-gap findings:', len(d)); assert len(d)==0, d"
```
Expected: suite rc=0; `run_instruction_eval coverage` ≥ 80 %; `repo-B coverage-gap findings: 0`.

- [ ] **Step 4: Commit** (repo-B):

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add tests/test_run_instruction_eval.py
git commit -m "test(b1): close run_instruction_eval coverage gap (33%->~95%) for coverage-gap convergence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: repo-P — close the `findings.py` gap (TDD)

**Files:** Modify `tests/test_findings_bridge.py` (repo-P, on `feat/phase2-b1`)

Target `scripts/perf_benchmark/findings.py` is pure/stdlib-only. Existing tests cover only the **explicit-triplet** path of `to_shared_findings`; the seven name-inference `_extract_*` handlers, `_build_finding`'s severity branch, and `_suggested_action`'s prescription matching are uncovered. Add tests using dimensions WITHOUT the explicit `metric`/`value`/`threshold` triplet but WITH the exact `_METRIC_EXTRACTORS` names and inference fields.

- [ ] **Step 1: Append the failing behaviour tests** to `tests/test_findings_bridge.py`:

```python
# --- name-inference extractors (no explicit metric triplet) ---
def test_extract_wall_time_from_cv() -> None:
    rubric = {"dimensions": [("Wall-Time Stability", {"tier": "FAIL", "cv": 7.0})]}
    result = findings.to_shared_findings(rubric, root="/r")
    assert len(result) == 1
    assert result[0]["metric"] == {"name": "wall_time_cv", "value": 7.0, "threshold": 3.0}
    assert result[0]["severity"] == "high"


def test_extract_cpu_emits_top_fn_and_ipc() -> None:
    rubric = {"dimensions": [("CPU Efficiency", {"tier": "WARN", "top_fn_pct": 35.0, "IPC": 0.8})]}
    result = findings.to_shared_findings(rubric, root="/r")
    assert {f["metric"]["name"] for f in result} == {"IPC", "top_fn_pct"}
    assert all(f["severity"] == "medium" for f in result)


def test_extract_l1_cache_from_worst_pct() -> None:
    rubric = {"dimensions": [("L1 Cache Efficiency", {"tier": "FAIL", "worst_pct": 9.0})]}
    result = findings.to_shared_findings(rubric, root="/r")
    assert result[0]["metric"] == {"name": "l1_miss_rate", "value": 9.0, "threshold": 1.0}


def test_extract_ll_cache_from_worst_pct() -> None:
    rubric = {"dimensions": [("Last-Level Cache", {"tier": "FAIL", "worst_pct": 3.0})]}
    result = findings.to_shared_findings(rubric, root="/r")
    assert result[0]["metric"]["name"] == "ll_miss_rate"


def test_extract_branch_from_worst_pct() -> None:
    rubric = {"dimensions": [("Branch Prediction", {"tier": "FAIL", "worst_pct": 4.0})]}
    result = findings.to_shared_findings(rubric, root="/r")
    assert result[0]["metric"]["name"] == "branch_mispred_rate"


def test_extract_algorithmic_only_emits_fail_and_warn_subchecks() -> None:
    rubric = {
        "dimensions": [
            (
                "Algorithmic Scaling",
                {
                    "tier": "FAIL",
                    "sub_checks": {
                        "time_complexity": {"tier": "FAIL", "k": 2.5},
                        "mem_complexity": {"tier": "PASS", "k": 1.0},
                    },
                },
            )
        ]
    }
    result = findings.to_shared_findings(rubric, root="/r")
    assert len(result) == 1
    assert result[0]["metric"]["name"] == "time_complexity"
    assert result[0]["metric"]["value"] == 2.5


def test_extract_memory_emits_peak_and_churn() -> None:
    rubric = {
        "dimensions": [("Memory Profile", {"tier": "WARN", "peak_bytes": 1024.0, "churn_peaks": 5.0})]
    }
    result = findings.to_shared_findings(rubric, root="/r")
    assert {f["metric"]["name"] for f in result} == {"churn_peaks", "peak_bytes"}


def test_unknown_dimension_without_triplet_emits_nothing() -> None:
    rubric = {"dimensions": [("Mystery Dimension", {"tier": "FAIL"})]}
    assert findings.to_shared_findings(rubric, root="/r") == []


def test_suggested_action_uses_prescription_when_source_matches() -> None:
    rubric = {
        "dimensions": [("CPU Efficiency", {"tier": "FAIL", "top_fn_pct": 50.0, "source": "CPU hotspot"})]
    }
    result = findings.to_shared_findings(rubric, root="/r")
    cpu = next(f for f in result if f["metric"]["name"] == "top_fn_pct")
    assert "hotspot" in cpu["suggested_action"].lower()


def test_suggested_action_falls_back_to_investigate() -> None:
    rubric = {"dimensions": [("Memory Profile", {"tier": "FAIL", "peak_bytes": 1.0})]}
    result = findings.to_shared_findings(rubric, root="/r")
    assert result[0]["suggested_action"].startswith("Investigate")
```

- [ ] **Step 2: Run the new tests — expect PASS:**

Run: `cd /home/jakub/projects/perf-benchmark-skill && python3 -m pytest tests/test_findings_bridge.py -q -p no:cacheprovider`
Expected: all PASS (old 7 + new 10). If a FAIL, the test encodes a wrong expectation — fix the test to match `findings.py`'s real behaviour (do NOT change the module).

- [ ] **Step 3: ruff-clean the changed test file** (repo-P CI's standalone format gate):

```bash
cd /home/jakub/projects/perf-benchmark-skill
~/.local/bin/ruff format --check tests/test_findings_bridge.py && ~/.local/bin/ruff check tests/test_findings_bridge.py
```
Expected: both clean. If format fails, run `~/.local/bin/ruff format tests/test_findings_bridge.py` and re-check.

- [ ] **Step 4: Verify the gap is closed (coverage > 50 %, target ≥ 80 %)**

```bash
cd /home/jakub/projects/perf-benchmark-skill
rm -rf /tmp/b1/repoP && mkdir -p /tmp/b1/repoP
cat > /tmp/b1/repoP/.coveragerc <<'RC'
[run]
parallel = true
data_file = /tmp/b1/repoP/.coverage
[report]
ignore_errors = true
RC
PYTHONPATH=/tmp/b1/cov-hook:$PYTHONPATH COVERAGE_PROCESS_START=/tmp/b1/repoP/.coveragerc \
  python3 -m coverage run --rcfile=/tmp/b1/repoP/.coveragerc -m pytest tests/ perf-optimization/tests/ -q -p no:cacheprovider >/tmp/b1/repoP/pytest.log 2>&1
echo "suite rc=$?"; tail -1 /tmp/b1/repoP/pytest.log
python3 -m coverage combine --rcfile=/tmp/b1/repoP/.coveragerc
python3 -m coverage json --rcfile=/tmp/b1/repoP/.coveragerc --data-file=/tmp/b1/repoP/.coverage -o /tmp/b1/repoP/coverage.json
python3 ~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  --root "$(pwd)" --source-prefix scripts --source-prefix perf-optimization/scripts \
  --coverage-json /tmp/b1/repoP/coverage.json --out-dir /tmp/b1/repoP/leaf
python3 -c "import json; d=json.load(open('/tmp/b1/repoP/coverage.json'))['files']['scripts/perf_benchmark/findings.py']['summary']; print('findings.py coverage:', round(d['percent_covered'],1),'%')"
python3 -c "import json; d=json.load(open('/tmp/b1/repoP/leaf/coverage-gap_findings.json')); print('repo-P coverage-gap findings:', len(d)); assert len(d)==0, d"
```
Expected: suite rc=0; `findings.py coverage` ≥ 80 %; `repo-P coverage-gap findings: 0`.

- [ ] **Step 5: Commit** (repo-P):

```bash
cd /home/jakub/projects/perf-benchmark-skill && git add tests/test_findings_bridge.py
git commit -m "test(b1): close findings.py coverage gap (47%->~95%) for coverage-gap convergence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Commit the reproducible recipe + before/after evidence (repo-B)

**Files:** Create `docs/superpowers/b1-evidence/recipe.md`, `docs/superpowers/b1-evidence/before-after.md`, copy leaf artifacts (repo-B)

- [ ] **Step 1: Copy the post-fix leaf finding artifacts to evidence**

```bash
E=/home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b1-evidence
cp /tmp/b1/repoB/leaf/coverage-gap_findings.json "$E/repoB-findings-after.json"
cp /tmp/b1/repoP/leaf/coverage-gap_findings.json "$E/repoP-findings-after.json"
```
Expected: both are `[]` (empty arrays).

- [ ] **Step 2: Write `docs/superpowers/b1-evidence/recipe.md`** with the exact per-repo commands:

````markdown
# B1 coverage-gap recipe (reproducible)

Subprocess-capture coverage is mandatory — plain `coverage run -m pytest` under-counts
subprocess-tested CLIs (repo-P `verify_win.py` shows 0% plain vs 96% with capture).

## Hook (once)
```bash
mkdir -p /tmp/b1/cov-hook
printf 'import coverage\ncoverage.process_startup()\n' > /tmp/b1/cov-hook/sitecustomize.py
```

## repo-A (verify-only — already gated at 0)
```bash
cd ~/projects/repo-audit-skills
python3 scripts/check_coverage_gap.py --coverage-json .self_audit_out/coverage/coverage.json
# -> {"status":"pass","count":0,"baseline":0}
```

## repo-B  (scope: scripts)  and  repo-P  (scope: scripts + perf-optimization/scripts)
```bash
RC=/tmp/b1/<repo>/.coveragerc       # [run] parallel=true, data_file=...  [report] ignore_errors=true
PYTHONPATH=/tmp/b1/cov-hook:$PYTHONPATH COVERAGE_PROCESS_START=$RC \
  python3 -m coverage run --rcfile=$RC -m pytest <suite dirs> -q -p no:cacheprovider
python3 -m coverage combine --rcfile=$RC
python3 -m coverage json --rcfile=$RC --data-file=<data_file> -o coverage.json
python3 ~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  --root <repo> <--source-prefix ...> --coverage-json coverage.json --out-dir <out>
```

`ignore_errors=true` is required: a subprocess may touch a non-UTF-8 out-of-scope fixture that
otherwise aborts `coverage json`. `--source-prefix` must name production dirs precisely
(repo-A uses `shared`, `scripts`, `skills/*/scripts`).
````

- [ ] **Step 3: Write `docs/superpowers/b1-evidence/before-after.md`**:

```markdown
# B1 coverage-gap convergence — before/after (2026-06-15, py3.14.4, coverage 7.14.1)

| repo | scope | before findings | action | after findings |
|------|-------|-----------------|--------|----------------|
| repo-A | shared,scripts,skills/*/scripts | 0 | verify-only (gate already converged) | 0 |
| repo-B | scripts | 1: run_instruction_eval.py 33.3% | +16 behaviour tests -> ~95% | 0 |
| repo-P | scripts,perf-optimization/scripts | 1: findings.py 47.5% | +10 behaviour tests -> ~95% | 0 |

Methodology note: subprocess-capture coverage is mandatory. Plain coverage falsely reported
repo-P verify_win.py 0% (real 96%) and select_candidate.py 39.8% (real 96%); only findings.py
(imported in-process) was a true gap. No accept entries added; close-not-accept (a coverage-gap
accept in repo-B/repo-P accept.json would be flagged stale by the report-stage wave partition).
Gate graduation deferred to B4.
```

- [ ] **Step 4: Commit** (repo-B):

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b1-evidence/
git commit -m "evidence(b1): coverage-gap recipe + before/after (all 3 repos converged to 0)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Verify gates + ship (merge to mains, real CI green, memory)

No releases (test/doc-only). But every pushed commit must keep CI — including the
`convergence-gate` job (repo-B, repo-P) — green.

- [ ] **Step 1: Pre-merge gate sims (the decisive local checks)**

```bash
# repo-B wave convergence gate must stay pass active 0
cd /home/jakub/projects/repo-audit-refactor-optimize && python3 scripts/check_wave_baseline.py 2>&1 | python3 -c "import json,sys; print(sys.stdin.read()[:400])"
# repo-P wave convergence gate
cd /home/jakub/projects/perf-benchmark-skill && python3 scripts/check_wave_baseline.py 2>&1 | python3 -c "import json,sys; print(sys.stdin.read()[:400])"
```
Expected: each prints `{"status":"pass","accepted":N,"active":0}`. **If `status != pass` or `active != 0` or any `stale_acceptances`, STOP** — a test-file addition unexpectedly tripped a wave lane (e.g. growth counting `tests/`); investigate before merging. (Growth audits the `scripts` scope, so `tests/` additions should NOT count — confirm here.)

- [ ] **Step 2: repo-B full suite + merge to main**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/ -q -p no:cacheprovider | tail -2
git checkout main && git merge --no-ff feat/phase2-b1 -m "Merge feat/phase2-b1: coverage-gap convergence (spec, plan, evidence, run_instruction_eval tests)" && git push origin main
```
Expected: suite green; merge + push succeed.

- [ ] **Step 3: repo-P full suite + ruff + merge to main**

```bash
cd /home/jakub/projects/perf-benchmark-skill
~/.local/bin/ruff format --check tests/ && ~/.local/bin/ruff check scripts/ tests/ perf-optimization/
python3 -m pytest tests/ perf-optimization/tests/ -q -p no:cacheprovider | tail -2
git checkout main && git merge --no-ff feat/phase2-b1 -m "Merge feat/phase2-b1: close findings.py coverage gap (coverage-gap convergence)" && git push origin main
```
Expected: ruff clean; suite green; merge + push succeed.

- [ ] **Step 4: Verify REAL CI green on every pushed main, incl. `convergence-gate`**

```bash
for r in repo-audit-refactor-optimize perf-benchmark-skill; do
  cd /home/jakub/projects/$r && echo "== $r ==" && gh run list --branch main --limit 2
done
```
Wait for completion (`gh run watch <id>` if in-progress). Expected: latest run on each `success`. If the `convergence-gate` job is red: `gh run view <id> --log-failed`, fix, do not leave a red gate. (repo-A unchanged — no push.)

- [ ] **Step 5: Delete merged work branches**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git branch -d feat/phase2-b1
cd /home/jakub/projects/perf-benchmark-skill && git branch -d feat/phase2-b1
```

- [ ] **Step 6: Update memory** — refresh `repo-audit-dogfood-loops` (+ `MEMORY.md` index): B1 SHIPPED — coverage-gap lane runs + converges on all 3 repos (A 0/verify, B & P each one gap closed by tests, ~95%); subprocess-capture coverage methodology established; no releases (test-only); gate graduation deferred to B4. Then proceed to **B2** (do NOT stop).

---

## Self-Review (planner)

- **Spec coverage:** §2 inventory → Tasks 1/2/3 (one per repo); §3 DONE → Task 2/3 (close > 50 %, target ≥ 80 %) + Task 1 (repo-A verify) + Task 4 (recipe/evidence) + Task 5 (CI green, memory); §4 subprocess capture → Tasks 2/3 Step-3/4 harness + Task 4 recipe; §5 close-not-accept → Tasks 2/3 add tests only, no accept.json touched; §6 gate-wiring-out → no gate added, Task 5 only verifies existing gates; §7 no-release → Task 5 merges without bump; §8 DoD → Task 5 Step 6.
- **Placeholder scan:** none — every test body, command, and expected output is concrete.
- **Type/identity consistency:** test symbols match the real modules read 2026-06-15 — repo-B `ev._load_expected` / `ev._load_model_findings` / `ev._build_parser` (arg `model_findings`, default `model`) / `ev.main`; repo-P `findings.to_shared_findings` + `_METRIC_EXTRACTORS` exact keys (`Wall-Time Stability`, `CPU Efficiency`, `L1 Cache Efficiency`, `Last-Level Cache`, `Branch Prediction`, `Algorithmic Scaling`, `Memory Profile`) and inference fields (`cv`, `top_fn_pct`, `IPC`, `worst_pct`, `sub_checks`, `peak_bytes`, `churn_peaks`). The `ev` alias is bound by the existing `import scripts.run_instruction_eval as ev` at the top of the repo-B test file; `findings` by the existing `importlib` load at the top of the repo-P test file.
- **Risk:** test-only additions tripping a growth lane → Task 5 Step 1 gate sim catches it pre-merge.
