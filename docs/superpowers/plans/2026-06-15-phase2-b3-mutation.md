# Phase 2 · B3 — mutation effectiveness on a hot module per repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run `test-effectiveness-audit` (mutmut) on one hot module per family repo, commit a mutation report per repo, add two genuine parser-contract tests to close repo-B's real gap (accepting the classified equivalent mutants), and record repo-P (clean) + repo-A (convention-blocked) decisions — no release.

**Architecture:** Measure-then-decide on an advisory mutation lane. Each target runs in a minimal `/tmp` staging root (module + its dedicated test) so the leaf's sandbox doesn't pull sibling-importing tests; no source is mutated in-place. Findings land in committed `b3-evidence/` (not `.repo-audit/accept.json` — a non-wave-lane accept would be flagged stale → RED gate, per B1/B2). Only repo-B's test file changes.

**Tech Stack:** Python 3.14, mutmut 3.6.0 via `test-effectiveness-audit` leaf (`repo-A/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py`), pytest, git.

**Spec:** `docs/superpowers/specs/2026-06-15-phase2-b3-mutation-design.md`

---

## Repo / path conventions

- **repo-A** = `/home/jakub/projects/repo-audit-skills` · **repo-B** = `/home/jakub/projects/repo-audit-refactor-optimize` (campaign home) · **repo-P** = `/home/jakub/projects/perf-benchmark-skill`
- **TEA** = `python3 /home/jakub/projects/repo-audit-skills/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py`
- Scratch/staging (gitignored): `/tmp/b3/` · Evidence (repo-B, committed): `docs/superpowers/b3-evidence/`

---

## File Structure

| File | Repo | Responsibility | Task |
|------|------|----------------|------|
| `docs/superpowers/b3-evidence/repoB-before.json`, `repoB-after.json` | B | repo-B mutation findings before/after | Tasks 1,2 |
| `docs/superpowers/b3-evidence/repoP-ledger.json` | B | repo-P CLEAN report | Task 1 |
| `docs/superpowers/b3-evidence/repoA-blocked.md` | B | repo-A mutmut-incompatibility finding + reproduction | Task 1 |
| `docs/superpowers/b3-evidence/report.md` | B | per-repo kill rates + survivor classification + decisions | Task 3 |
| `tests/test_mine_iteration_kpis.py` | B | +2 parser-contract tests | Task 2 |

No production source changes; no `.repo-audit/accept.json`; no `SKILL.md`/version/CHANGELOG.

---

## Task 0: Setup

- [ ] **Step 1:** Confirm repo-B branch: `cd /home/jakub/projects/repo-audit-refactor-optimize && git branch --show-current` → `feat/phase2-b3`.
- [ ] **Step 2:** `mkdir -p /tmp/b3 docs/superpowers/b3-evidence`.

---

## Task 1: Capture the three mutation reports as evidence (measurement)

**Files:** Create `docs/superpowers/b3-evidence/{repoB-before.json,repoP-ledger.json,repoA-blocked.md}`

- [ ] **Step 1: repo-B baseline mutation** (`mine_iteration_kpis.py`, natively mutmut-compatible — test does `import scripts.mine_iteration_kpis`):

```bash
S=/tmp/b3/stageB && rm -rf $S && mkdir -p $S/scripts $S/tests
cp /home/jakub/projects/repo-audit-refactor-optimize/scripts/mine_iteration_kpis.py $S/scripts/
cp /home/jakub/projects/repo-audit-refactor-optimize/tests/test_mine_iteration_kpis.py $S/tests/
printf 'scripts/mine_iteration_kpis.py\n' > /tmp/b3/paths-B.txt
python3 /home/jakub/projects/repo-audit-skills/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py \
  --root $S --source-prefix scripts --paths /tmp/b3/paths-B.txt --tests-dir tests \
  --max-mutants 600 --out-dir /tmp/b3/repoB-before --format json
cp /tmp/b3/repoB-before/*findings*.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b3-evidence/repoB-before.json
python3 -c "import json,glob; d=json.load(open(glob.glob('/tmp/b3/repoB-before/*findings*.json')[0])); print('repo-B kill_rate:', d[0]['metric']['value'])"
```
Expected: `repo-B kill_rate: 0.671` (a TEST finding, < 0.8).

- [ ] **Step 2: repo-P mutation** (`ledger.py` — needs path-aligned staging so the test's `perf_benchmark.ledger` import matches mutmut's key; the staged test's `SCRIPTS_DIR` is pointed at the staging root):

```bash
S=/tmp/b3/stageP && rm -rf $S && mkdir -p $S/perf_benchmark $S/tests
cp /home/jakub/projects/perf-benchmark-skill/scripts/perf_benchmark/__init__.py $S/perf_benchmark/ 2>/dev/null || touch $S/perf_benchmark/__init__.py
cp /home/jakub/projects/perf-benchmark-skill/scripts/perf_benchmark/ledger.py $S/perf_benchmark/
sed 's#parents\[1\] */ *"scripts"#parents[1]#; s#parents\[1\]/"scripts"#parents[1]#' \
  /home/jakub/projects/perf-benchmark-skill/tests/test_ledger.py > $S/tests/test_ledger.py
printf 'perf_benchmark/ledger.py\n' > /tmp/b3/paths-P.txt
python3 /home/jakub/projects/repo-audit-skills/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py \
  --root $S --source-prefix perf_benchmark --paths /tmp/b3/paths-P.txt --tests-dir tests \
  --max-mutants 500 --out-dir /tmp/b3/repoP --format json
cp /tmp/b3/repoP/*findings*.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b3-evidence/repoP-ledger.json
python3 -c "import json,glob; fs=glob.glob('/tmp/b3/repoP/*findings*.json'); d=json.load(open(fs[0])); print('repo-P ledger findings:', len(d), '(0 = CLEAN, kill rate >= 0.8)')"
```
Expected: `repo-P ledger findings: 0 (0 = CLEAN, kill rate >= 0.8)`.

- [ ] **Step 3: repo-A reproduction of the convention block** — capture the mutmut failure on a representative repo-A leaf to prove the `spec_from_file_location`/`helpers.load_module` incompatibility:

```bash
S=/tmp/b3/stageA && rm -rf $S && mkdir -p $S/scripts $S/tests
cp /home/jakub/projects/repo-audit-skills/skills/coverage-gap-audit/scripts/coverage_gap_audit.py $S/scripts/
cp /home/jakub/projects/repo-audit-skills/skills/coverage-gap-audit/scripts/health_common.py $S/scripts/
cp /home/jakub/projects/repo-audit-skills/skills/coverage-gap-audit/tests/test_coverage_gap_findings.py $S/tests/ 2>/dev/null
printf 'scripts/coverage_gap_audit.py\n' > /tmp/b3/paths-A.txt
python3 /home/jakub/projects/repo-audit-skills/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py \
  --root $S --source-prefix scripts --paths /tmp/b3/paths-A.txt --tests-dir tests \
  --max-mutants 500 --out-dir /tmp/b3/repoA --format json > /tmp/b3/repoA.out 2>&1 || true
# record the failure mode (trampoline / spec_from_file) + the convention census
python3 - <<'PY'
import subprocess, pathlib
out = pathlib.Path("/tmp/b3/repoA.out").read_text()[:600]
census = subprocess.run(["bash","-lc","grep -rl 'load_module\\|spec_from_file_location' /home/jakub/projects/repo-audit-skills/skills/*/tests /home/jakub/projects/repo-audit-skills/tests 2>/dev/null | wc -l"], capture_output=True, text=True).stdout.strip()
md = f"""# repo-A — mutation BLOCKED by the spec_from_file_location test convention

repo-A's leaf tests load modules via `helpers.load_module()` /
`importlib.util.spec_from_file_location` ({census} test files). mutmut 3.x instruments
source through a runtime trampoline that `spec_from_file_location` bypasses, so it cannot
correlate test execution with mutants. Representative reproduction (coverage-gap-audit leaf):

```
{out.strip()}
```

**Decision: ACCEPT** — the convention is a deliberate design choice (leaves are testable without
packaging/installation). Native mutation testing of repo-A would require rewriting ~{census} test
files to normal package imports whose dotted path matches mutmut's mutant key. Logged as a future
candidate (its own brainstorm→plan→ship); NOT done in B3.
"""
pathlib.Path("/home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b3-evidence/repoA-blocked.md").write_text(md)
print("wrote repoA-blocked.md; census files:", census)
PY
```
Expected: `repoA-blocked.md` written; the captured output shows a trampoline/`spec_from_file` error or a collection ImportError (the convention block).

- [ ] **Step 4: Commit the raw evidence:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b3-evidence/
git commit -m "evidence(b3): mutation reports — repo-B 0.671, repo-P clean, repo-A convention-blocked

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Close repo-B's real gap with two parser-contract tests

**Files:** Modify `tests/test_mine_iteration_kpis.py` (repo-B). The existing test already does
`import scripts.mine_iteration_kpis as m`. The two tests assert every `_build_parser()` default and
an all-flags-set parse — killing the **behavioral** parser mutants (the equivalent help-string
mutants are intentionally left, see spec §3).

- [ ] **Step 1: Add `from pathlib import Path`** to the imports of `tests/test_mine_iteration_kpis.py` if not already present (the new tests compare `Path` defaults).

- [ ] **Step 2: Append the two tests** to `tests/test_mine_iteration_kpis.py`:

```python
def test_build_parser_defaults_and_dests():
    p = m._build_parser()
    ns = p.parse_args([])
    assert ns.iteration == 0
    assert ns.repo == Path(".")
    assert ns.start_sha is None
    assert ns.end_sha is None
    assert ns.baseline == ".repo-audit/accept.json"
    assert ns.runs_dir == Path("/tmp/sp13/runs")
    assert ns.kpi_file == Path("scripts/iteration_kpis.jsonl")
    assert ns.repo_name is None


def test_build_parser_explicit_args():
    p = m._build_parser()
    ns = p.parse_args([
        "--iteration", "5", "--repo", "/x", "--start-sha", "aaa", "--end-sha", "bbb",
        "--baseline", "b.json", "--runs-dir", "/r", "--kpi-file", "k.jsonl",
        "--repo-name", "repo-b",
    ])
    assert ns.iteration == 5
    assert ns.repo == Path("/x")
    assert ns.start_sha == "aaa"
    assert ns.end_sha == "bbb"
    assert ns.baseline == "b.json"
    assert ns.runs_dir == Path("/r")
    assert ns.kpi_file == Path("k.jsonl")
    assert ns.repo_name == "repo-b"
```

- [ ] **Step 3: Run the file — expect PASS:**

Run: `cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/test_mine_iteration_kpis.py -q -p no:cacheprovider`
Expected: all PASS (existing + 2 new). If a FAIL, a default assertion is wrong — read `scripts/mine_iteration_kpis.py:282-317` `_build_parser` and correct the test to the real default (never change the module).

- [ ] **Step 4: Re-measure mutation** (confirm the behavioral mutants are killed; residual = equivalents):

```bash
S=/tmp/b3/stageB && cp /home/jakub/projects/repo-audit-refactor-optimize/tests/test_mine_iteration_kpis.py $S/tests/
python3 /home/jakub/projects/repo-audit-skills/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py \
  --root $S --source-prefix scripts --paths /tmp/b3/paths-B.txt --tests-dir tests \
  --max-mutants 600 --out-dir /tmp/b3/repoB-after --format json || true
cp /tmp/b3/repoB-after/*findings*.json /home/jakub/projects/repo-audit-refactor-optimize/docs/superpowers/b3-evidence/repoB-after.json 2>/dev/null
python3 -c "
import json,glob
fs=glob.glob('/tmp/b3/repoB-after/*findings*.json')
d=json.load(open(fs[0])) if fs else []
if d:
    print('repo-B AFTER kill_rate:', d[0]['metric']['value'])
    raw=d[0]['evidence']['raw']
    import re
    funcs={re.sub(r'__mutmut_\d+$','',s.split('=')[0]).split('.x__')[-1] for s in raw.split(';') if 'survived' in s}
    print('residual survivor functions:', funcs)
else:
    print('repo-B AFTER: CLEAN (0 findings)')
"
```
Expected: kill rate ~0.70; **all residual survivors in `_build_parser`** (the equivalent help-string mutants per spec §3). This confirms the behavioral parser mutants are now killed and only equivalents remain.

- [ ] **Step 5: Commit** (test only):
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add tests/test_mine_iteration_kpis.py docs/superpowers/b3-evidence/repoB-after.json
git commit -m "test(b3): assert _build_parser defaults/dests (kill behavioral mutants; residual = equivalent help-string mutants)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Write the consolidated mutation report + decisions

**Files:** Create `docs/superpowers/b3-evidence/report.md` (repo-B)

- [ ] **Step 1: Write `report.md`** capturing:
  - **Per-repo kill rates:** repo-B `mine_iteration_kpis.py` 0.671 → ~0.70 (after); repo-P
    `ledger.py` CLEAN (≥ 0.8); repo-A BLOCKED.
  - **repo-B survivor classification** (all 10 equivalent): `mutmut_13/101/104` remove a `help=`
    string; `mutmut_107/108/109/110/111/112` mutate `--repo-name` help text; `mutmut_103` removes a
    behaviorally-redundant `default=None`. **Decision:** the two parser-contract tests close the real
    behavioral gap (defaults/types/dests now asserted); the residual equivalents are **ACCEPTED**
    (killing them needs brittle help-text assertions → rejected as advisory-metric gaming).
  - **repo-P decision:** CLEAN → **no action**.
  - **repo-A decision:** mutation **BLOCKED** by the `spec_from_file_location`/`helpers.load_module`
    convention (94 files) → **ACCEPT** the limitation; convention change logged as a future
    candidate (not B3).
  - **Methodology finding:** mutmut 3.x requires the test's import dotted-path == the mutant key
    (path from source root) **and** forbids `spec_from_file_location`; this gates family
    mutation-testability. Recommend the mutation lane **stay Tier-2 advisory** (input for B4).
  - **Convergence statement:** a mutation report exists per repo; every finding is terminal-decided;
    no `.repo-audit/accept.json` change; no release.

- [ ] **Step 2: Commit:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && git add docs/superpowers/b3-evidence/report.md
git commit -m "evidence(b3): consolidated mutation report + close/accept decisions per repo

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Verify gates + ship (merge repo-B, real CI green, memory)

Only repo-B changed (test + docs) → no release.

- [ ] **Step 1: repo-B pre-merge wave-gate sim (pinned jscpd):**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
test -x /tmp/b1/leaves/node_modules/.bin/jscpd || (git clone --depth 1 --branch v0.7.2 https://github.com/jc1122/repo-audit-skills.git /tmp/b1/leaves && cd /tmp/b1/leaves && npm ci)
WAVE_RUNNER="$(pwd)/scripts/run_diagnosis_wave.py" SKILLS_ROOT=/tmp/b1/leaves/skills \
  PATH="/tmp/b1/leaves/node_modules/.bin:$PATH" python3 scripts/check_wave_baseline.py | tail -6
```
Expected: `{"status":"pass","accepted":N,"active":0}`. If not pass / active≠0 / any stale, STOP and investigate.

- [ ] **Step 2: repo-B full suite + merge + push:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && python3 -m pytest tests/ -q -p no:cacheprovider | tail -2
git checkout main && git merge --no-ff feat/phase2-b3 -m "Merge feat/phase2-b3: mutation effectiveness on a hot module per repo (evidence + _build_parser tests)" && git push origin main
```
Expected: suite green (307 — 305 + 2 new); merge + push succeed.

- [ ] **Step 3: Verify REAL CI green incl. `convergence-gate`:**
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize && gh run list --branch main --limit 1
# gh run watch <id> --exit-status ; then:
gh run view <id> --json jobs -q '.jobs[] | "\(.name): \(.conclusion)"'
```
Expected: `check: success`, `convergence-gate: success`.

- [ ] **Step 4: Delete branch:** `git branch -d feat/phase2-b3`.

- [ ] **Step 5: Update memory** — refresh `repo-audit-dogfood-loops` (+ `MEMORY.md`): B3 SHIPPED — mutation per repo: repo-B mine_iteration_kpis 0.671 (10 survivors all equivalent argparse help-string mutants; +2 parser-contract tests kill the behavioral ones, equivalents accepted), repo-P ledger CLEAN ≥0.8, repo-A BLOCKED (spec_from_file convention, 94 files — accept + future candidate); mutmut 3.x needs import-path==mutant-key + no spec_from_file; no release. Then proceed to **B4** (do NOT stop).

---

## Self-Review (planner)

- **Spec coverage:** §3 measured results → Task 1 (all three reports); §4.2 repo-B close → Task 2 (2 tests + re-measure); §4.3 repo-P clean → Task 1 Step 2 + Task 3; §4.4 repo-A blocked → Task 1 Step 3 + Task 3; §2 methodology → Task 3; §7 ship/no-release → Task 4; §8 DoD → Task 4 Step 5.
- **Placeholder scan:** none — the two test bodies are concrete and pre-validated on staging; every command + expected output is exact. (`<id>` in Task 4 Step 3 is a runtime gh run id.)
- **Type/identity consistency:** `m._build_parser()` and the asserted defaults match `scripts/mine_iteration_kpis.py:282-317` read 2026-06-15 (`iteration=0`, `repo=Path(".")`, `baseline=".repo-audit/accept.json"`, `runs_dir=Path("/tmp/sp13/runs")`, `kpi_file=Path("scripts/iteration_kpis.jsonl")`, `repo_name=None`); `m` is the existing `import scripts.mine_iteration_kpis as m`. TEA flags match the leaf `--help`.
- **Risk:** a wrong default in a test → Task 2 Step 3 targeted run catches it; the repo-P staged sys.path tweak is a documented measurement accommodation; test-only additions tripping a wave lane → Task 4 Step 1 pinned-jscpd sim catches it pre-merge.
