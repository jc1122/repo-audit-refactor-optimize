# Phase 2 · B2 — test-* lanes on the family suites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run `test-quality-assurance` (TQA), `test-redundancy-triage` (TRT), and the `test-audit-pipeline` umbrella on the family's own suites; triage every finding to a terminal decision (measured: 0 safe DELETE, structural TQA dims justified); apply ONE genuine bounded assertion-quality improvement (5 `match=` additions in repo-B); commit reports + a `triage.md`; no release.

**Architecture:** Measure-then-triage on advisory lanes. The lanes only run + report (read-only) on all three repos; the single suite change is repo-B test-only. Findings land in committed `b2-evidence/` (not `.repo-audit/accept.json` — a non-wave-lane accept would be flagged stale → RED gate, per B1). TQA uses honest invocation (subprocess-capture coverage **with `--branch`**, fed via `--cov-json`).

**Tech Stack:** Python 3.14, pytest, coverage.py 7.14.1, the three installed leaves (`audit_test_quality.py`, `triage_redundancy.py`, `audit_pipeline.py`), git + `gh`.

**Spec:** `docs/superpowers/specs/2026-06-15-phase2-b2-test-lanes-design.md`

---

## Repo / path conventions

- **repo-A** = `/home/jakub/projects/repo-audit-skills` · **repo-B** = `/home/jakub/projects/repo-audit-refactor-optimize` (campaign home) · **repo-P** = `/home/jakub/projects/perf-benchmark-skill`
- **TQA** = `python3 repo-A/skills/test-quality-assurance/scripts/audit_test_quality.py`
- **TRT** = `python3 repo-A/skills/test-redundancy-triage/scripts/triage_redundancy.py`
- **PIPE** = `python3 repo-A/skills/test-audit-pipeline/scripts/audit_pipeline.py`
- Scratch (gitignored): `/tmp/b2/` · Evidence (repo-B, committed): `docs/superpowers/b2-evidence/`
- Subprocess hook (from B1, reused): `/tmp/b1/cov-hook/sitecustomize.py`

---

## File Structure

| File | Repo | Responsibility | Task |
|------|------|----------------|------|
| `docs/superpowers/b2-evidence/tqa-{repoA,repoB,repoP}.{json,md}` | B | TQA rubric reports | Task 1 |
| `docs/superpowers/b2-evidence/trt-{repoA,repoB,repoP}/` | B | TRT triage reports (key CSVs/JSON) | Task 2 |
| `docs/superpowers/b2-evidence/pipeline-repoB/` | B | test-audit-pipeline unified report | Task 3 |
| `tests/test_run_instruction_eval.py` | B | +5 `match=` on error-path raises | Task 4 |
| `docs/superpowers/b2-evidence/triage.md` | B | per-finding terminal decisions + churn-decline | Task 5 |

Only repo-B's `tests/` changes; repo-A and repo-P are read-only lane runs. No production source, no `.repo-audit/accept.json`, no `SKILL.md`/version/CHANGELOG.

---

## Task 0: Setup + green baselines

- [ ] **Step 1:** Confirm repo-B branch: `cd /home/jakub/projects/repo-audit-refactor-optimize && git branch --show-current` → `feat/phase2-b2`. (repo-A/repo-P need NO branch — read-only.)
- [ ] **Step 2:** Make dirs: `mkdir -p /tmp/b2 /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b2-evidence`. Confirm the B1 hook exists: `test -f /tmp/b1/cov-hook/sitecustomize.py || printf 'import coverage\ncoverage.process_startup()\n' > /tmp/b1/cov-hook/sitecustomize.py`.
- [ ] **Step 3:** Confirm suites green: repo-B `python3 -m pytest tests/ -q` (305), repo-P `python3 -m pytest tests/ perf-optimization/tests/ -q` (176), repo-A leaf `python3 -m pytest skills/coverage-gap-audit/tests/ -q` (13). If RED, STOP.

---

## Task 1: TQA (honest) on all three repos

**Files:** Create `docs/superpowers/b2-evidence/tqa-{repoA,repoB,repoP}.{json,md}` (repo-B)

- [ ] **Step 1: Regenerate branch-enabled coverage.json per repo** (subprocess capture + `--branch`):

```bash
gen_cov () {  # $1=repo abs  $2=out  $3..=suite dirs
  local repo="$1" out="$2"; shift 2
  rm -rf "$out" && mkdir -p "$out"
  printf '[run]\nbranch = true\nparallel = true\ndata_file = %s/.coverage\n[report]\nignore_errors = true\n' "$out" > "$out/.coveragerc"
  ( cd "$repo" && PYTHONPATH=/tmp/b1/cov-hook:$PYTHONPATH COVERAGE_PROCESS_START="$out/.coveragerc" \
      python3 -m coverage run --rcfile="$out/.coveragerc" -m pytest "$@" -q -p no:cacheprovider >"$out/pytest.log" 2>&1 )
  ( cd "$repo" && python3 -m coverage combine --rcfile="$out/.coveragerc" >/dev/null 2>&1
    python3 -m coverage json --rcfile="$out/.coveragerc" --data-file="$out/.coverage" -o "$out/coverage.json" >/dev/null 2>&1 )
  echo "$out/coverage.json: $(python3 -c "import json;print(len(json.load(open('$out/coverage.json'))['files']),'files')")"
}
gen_cov /home/jakub/projects/repo-audit-refactor-optimize /tmp/b2/covB tests
gen_cov /home/jakub/projects/perf-benchmark-skill        /tmp/b2/covP tests perf-optimization/tests
gen_cov /home/jakub/projects/repo-audit-skills           /tmp/b2/covA tests
```
Expected: each prints a file count. (repo-A `tests` is the top-level suite; leaf suites are audited separately — this is a representative honest run, not a full repo-A sweep.)

- [ ] **Step 2: Run TQA with `--cov-json`** for each repo, writing reports straight into evidence:

```bash
E=/home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b2-evidence
TQA=/home/jakub/projects/repo-audit-skills/skills/test-quality-assurance/scripts/audit_test_quality.py
python3 $TQA --root /home/jakub/projects/repo-audit-refactor-optimize --tests-dir tests \
  --cov-json /tmp/b2/covB/coverage.json --json-out $E/tqa-repoB.json --md-out $E/tqa-repoB.md
python3 $TQA --root /home/jakub/projects/perf-benchmark-skill --tests-dir tests,perf-optimization/tests \
  --cov-json /tmp/b2/covP/coverage.json --json-out $E/tqa-repoP.json --md-out $E/tqa-repoP.md
python3 $TQA --root /home/jakub/projects/repo-audit-skills --tests-dir tests \
  --cov-json /tmp/b2/covA/coverage.json --json-out $E/tqa-repoA.json --md-out $E/tqa-repoA.md
for r in A B C; do :; done
python3 - <<'PY'
import json
for r in ("repoA","repoB","repoP"):
    d=json.load(open(f"/home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b2-evidence/tqa-{r}.json"))["rubric_scores"]
    print(f"{r}: {d['total']}/{d['max_total']}  ", {k:v['score'] for k,v in d.items() if isinstance(v,dict)})
PY
```
Expected: three rubric totals printed (repo-B ≈ 11–12/24 with branch coverage). Record the per-dimension scores for `triage.md`.

- [ ] **Step 3: Commit** the TQA evidence:
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b2-evidence/tqa-*
git commit -m "evidence(b2): TQA rubric reports (honest, branch coverage) for all 3 repos

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: TRT on one tractable target per repo

**Files:** Create `docs/superpowers/b2-evidence/trt-{repoA,repoB,repoP}/` (key artifacts only) (repo-B)

- [ ] **Step 1: Run TRT (default non-strict gate) on each target:**

```bash
TRT=/home/jakub/projects/repo-audit-skills/skills/test-redundancy-triage/scripts/triage_redundancy.py
# repo-P (≈20s)
python3 $TRT --root /home/jakub/projects/perf-benchmark-skill \
  --suite perf-optimization/tests/test_select_candidate.py \
  --source-prefix perf-optimization/scripts --out-dir /tmp/b2/trt-repoP --max-workers 4
# repo-B (B1 file, self-dogfood)
python3 $TRT --root /home/jakub/projects/repo-audit-refactor-optimize \
  --suite tests/test_run_instruction_eval.py --source-prefix scripts \
  --out-dir /tmp/b2/trt-repoB --max-workers 4
# repo-A (one leaf suite, 4 files)
python3 $TRT --root /home/jakub/projects/repo-audit-skills \
  --suite skills/coverage-gap-audit/tests/test_coverage_gap_cli.py \
  --suite skills/coverage-gap-audit/tests/test_coverage_gap_findings.py \
  --suite skills/coverage-gap-audit/tests/test_coverage_gap_idempotent.py \
  --suite skills/coverage-gap-audit/tests/test_coverage_gap_relpaths.py \
  --source-prefix skills/coverage-gap-audit/scripts --out-dir /tmp/b2/trt-repoA --max-workers 4
```
Expected: each completes (≤~60s). Read each `candidate_validation_summary.json` `counts` — record DELETE/MERGE/KEEP per repo. **Conservative rule:** act on a removal ONLY if a row is a strict-gate-passing DELETE AND a full suite re-run + coverage-gap re-audit stay green. (Measured on the probe: 0 DELETE; expect the same.)

- [ ] **Step 2: Copy the decision artifacts to evidence** (not the bulky matrices):
```bash
E=/home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b2-evidence
for r in repoA repoB repoP; do
  mkdir -p $E/trt-$r
  cp /tmp/b2/trt-$r/candidate_validation_summary.json $E/trt-$r/ 2>/dev/null
  cp /tmp/b2/trt-$r/candidate_validation.md $E/trt-$r/ 2>/dev/null
done
python3 -c "
import json
for r in ('repoA','repoB','repoP'):
    d=json.load(open(f'/home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b2-evidence/trt-{r}/candidate_validation_summary.json'))
    print(r, d.get('counts'), 'baseline_pass=', d.get('baseline_pass'))
"
```
Expected: counts printed; `baseline_pass=True` each. Record.

- [ ] **Step 3: Commit:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b2-evidence/trt-*
git commit -m "evidence(b2): TRT triage reports (3 tractable targets; conservative, 0 safe DELETE)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: test-audit-pipeline umbrella (one demonstration)

**Files:** Create `docs/superpowers/b2-evidence/pipeline-repoB/` (repo-B)

- [ ] **Step 1: Run the umbrella on a bounded repo-B suite** (coverage → TQA + triage → unified report):
```bash
PIPE=/home/jakub/projects/repo-audit-skills/skills/test-audit-pipeline/scripts/audit_pipeline.py
python3 $PIPE --root /home/jakub/projects/repo-audit-refactor-optimize \
  --suite tests/test_run_instruction_eval.py --source-prefix scripts \
  --out-dir /tmp/b2/pipe-repoB --max-workers 4
ls /tmp/b2/pipe-repoB/
```
Expected: a unified report (e.g. `pipeline_report.md`/`.json`) + the stage artifacts. If the umbrella errors on an env detail, capture the error in the evidence and fall back to noting the two leaves already ran standalone (Tasks 1–2) — the umbrella demo is a nice-to-have, not a blocker.

- [ ] **Step 2: Copy the top-level report to evidence + commit:**
```bash
E=/home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b2-evidence
mkdir -p $E/pipeline-repoB
cp /tmp/b2/pipe-repoB/*.md /tmp/b2/pipe-repoB/*.json $E/pipeline-repoB/ 2>/dev/null
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b2-evidence/pipeline-repoB
git commit -m "evidence(b2): test-audit-pipeline umbrella demo on repo-B

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Apply the one genuine bounded improvement (repo-B `match=`)

**Files:** Modify `tests/test_run_instruction_eval.py` (repo-B, `feat/phase2-b2`)

These five error-path tests assert a **stable contract message**; adding `match=` makes them assert the *right* error, not merely the type — a genuine Assertion-Quality improvement (not rubric-chasing). repo-P/repo-A get NO change (repo-P's only raises are `pytest.raises(SystemExit)` from argparse — `match=` on an exit code adds no contract value; pre-existing repo-A raises are out of scope as wholesale churn — recorded in `triage.md`).

- [ ] **Step 1: Apply the five edits** in `tests/test_run_instruction_eval.py`:

| test function | change |
|---|---|
| `test_load_expected_missing_file_raises` | `pytest.raises(ValueError)` → `pytest.raises(ValueError, match="neither an int nor an existing file")` |
| `test_load_expected_bool_json_raises` | `pytest.raises(ValueError)` → `pytest.raises(ValueError, match="not an int payload")` |
| `test_load_expected_bad_dict_raises` | `pytest.raises(ValueError)` → `pytest.raises(ValueError, match="must be an int or")` |
| `test_load_model_findings_missing_raises` | `pytest.raises(ValueError)` → `pytest.raises(ValueError, match="file does not exist")` |
| `test_load_model_findings_non_array_raises` | `pytest.raises(ValueError)` → `pytest.raises(ValueError, match="must be a JSON array")` |

(Each `match` substring is a plain literal — no regex metacharacters — and is taken verbatim from the `raise ValueError(...)` messages in `scripts/run_instruction_eval.py`.)

- [ ] **Step 2: Run the file — expect PASS** (the asserted messages are the real ones):

Run: `cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/test_run_instruction_eval.py -q -p no:cacheprovider`
Expected: 18 PASS. If a `match` FAILS, the substring is wrong — read the real message in `scripts/run_instruction_eval.py` and fix the test's `match` (never the module).

- [ ] **Step 3: Re-measure TQA Assertion Quality** for repo-B:
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
python3 /home/jakub/projects/repo-audit-skills/skills/test-quality-assurance/scripts/audit_test_quality.py \
  --root "$(pwd)" --tests-dir tests --cov-json /tmp/b2/covB/coverage.json --json-out /tmp/b2/tqa-repoB-after.json
python3 -c "import json; d=json.load(open('/tmp/b2/tqa-repoB-after.json'))['rubric_scores']['Assertion Quality']; print('Assertion Quality:', d['score'],'/3 —', d['rationale'])"
```
Expected: the raises-with-match ratio rises (8/26 → 13/26 = 0.5); record the new score (it may or may not cross to 2/3 — the improvement is genuine regardless).

- [ ] **Step 4: Commit:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add tests/test_run_instruction_eval.py
git commit -m "test(b2): sharpen run_instruction_eval error-path assertions with match= (TQA assertion quality)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: triage.md — record every terminal decision

**Files:** Create `docs/superpowers/b2-evidence/triage.md` (repo-B)

- [ ] **Step 1: Write `triage.md`** capturing, from the committed reports:
  - **TQA per-repo rubric** (totals + each sub-3 dimension) with a one-line classification of every <3 dimension as **ARTIFACT** (structural: script-module white-box testing / no package API / N/A non-functional) or **GENUINE** (Assertion Quality). State the honest conclusion: the family suites are well-curated; low dims are dominated by the white-box-leaf-testing context, not defects.
  - **TRT per-repo counts** (DELETE/MERGE/KEEP) with the terminal decision: **0 safe DELETE** (conservative, default gate); MERGE candidates **KEEP** (legitimate parametrize-style variants, "delete gates not fully satisfied"); the 183 s `test-redundancy-triage` suite is **excluded from TRT** as impractical (TRT re-runs the target many times) — recorded, not a gap.
  - **The one applied improvement** (5 `match=`) + the **explicit decline** of a wholesale `match=` sweep across pre-existing tests as low-value churn / rubric-chasing.
  - **Convergence statement:** all three lanes ran on the family; every finding is terminal-decided; no `.repo-audit/accept.json` change (would be stale → RED); gate graduation deferred to B4.

- [ ] **Step 2: Commit:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b2-evidence/triage.md
git commit -m "evidence(b2): triage.md — terminal decisions for TQA/TRT findings across the family

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Verify gates + ship (merge repo-B, real CI green, memory)

Only repo-B changed (test + docs) → no release. repo-A/repo-P untouched (read-only lane runs).

- [ ] **Step 1: repo-B pre-merge wave-gate sim with pinned jscpd** (the B1-proven decisive check):
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
test -x /tmp/b1/leaves/node_modules/.bin/jscpd || (git clone --depth 1 --branch v0.7.2 https://github.com/jc1122/repo-audit-skills.git /tmp/b1/leaves && cd /tmp/b1/leaves && npm ci)
WAVE_RUNNER="$(pwd)/scripts/run_diagnosis_wave.py" SKILLS_ROOT=/tmp/b1/leaves/skills \
  PATH="/tmp/b1/leaves/node_modules/.bin:$PATH" python3 scripts/check_wave_baseline.py | tail -6
```
Expected: `{"status":"pass","accepted":N,"active":0}`. If `status != pass` / `active != 0` / any `stale_acceptances`, STOP and investigate (docs + test additions should not touch the `scripts`-scoped wave lanes).

- [ ] **Step 2: repo-B full suite + merge to main + push:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/ -q -p no:cacheprovider | tail -2
git checkout main && git merge --no-ff feat/phase2-b2 -m "Merge feat/phase2-b2: test-* lanes on the family suites (TQA/TRT/pipeline evidence + match= sharpening)" && git push origin main
```
Expected: 305 pass; merge + push succeed.

- [ ] **Step 3: Verify REAL CI green incl. `convergence-gate`:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && gh run list --branch main --limit 1
# gh run watch <id> --exit-status ; then:
gh run view <id> --json jobs -q '.jobs[] | "\(.name): \(.conclusion)"'
```
Expected: `check: success`, `convergence-gate: success`. If red, `gh run view <id> --log-failed`, fix, do not leave a red gate.

- [ ] **Step 4: Delete the merged branch:** `cd /home/jakub/projects/repo-audit-refactor-optimize && git branch -d feat/phase2-b2`.

- [ ] **Step 5: Update memory** — refresh `repo-audit-dogfood-loops` (+ `MEMORY.md`): B2 SHIPPED — TQA/TRT/test-audit-pipeline run + converged (honest triage) on all 3 repos; family suites already well-curated (TRT 0 safe DELETE; TQA low dims = white-box-leaf-testing artifacts, justified); one genuine `match=` assertion improvement in repo-B; no release; B3/B4 pending. Then proceed to **B3** (do NOT stop).

---

## Self-Review (planner)

- **Spec coverage:** §3.1 TQA-honest → Task 1; §3.2 TRT-bounded → Task 2; §3.3 pipeline → Task 3; §3.4 terminal decisions → Task 5; §3.5 one bounded improvement → Task 4 (+ honest-empty fallback in Step 2); §7 ship/no-release → Task 6; §8 DoD → Task 6 Step 5.
- **Placeholder scan:** none — every command, target, and the five exact `match=` substrings are concrete. (`<id>` in Task 6 Step 3 is a runtime gh run id, not a plan placeholder.)
- **Type/identity consistency:** the five `match=` substrings are verbatim fragments of the `raise ValueError(...)` strings in `scripts/run_instruction_eval.py:104,107,112,119,122`; TRT/TQA/PIPE flags match each leaf's real `--help` read 2026-06-15.
- **Risk:** (a) a wrong `match=` substring → Task 4 Step 2 targeted run catches it; (b) test/doc additions tripping a wave lane → Task 6 Step 1 pinned-jscpd sim catches it pre-merge; (c) the umbrella erroring on an env detail → Task 3 Step 1 fallback keeps B2 unblocked (the two leaves already ran standalone).
