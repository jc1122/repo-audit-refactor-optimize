# Phase 3 · C2 — perf-smell-audit high-precision narrowing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** Narrow `perf-smell-audit` to perflint's high-precision codes (drop the over-approximating
loop-invariant heuristic trio W8201/W8202/W8205 + dead R8203), ship repo-A v0.7.5, then re-pin
repo-B/repo-P convergence gates to v0.7.5 and prune the 49 now-stale perf-smell accepts.

**Architecture:** Replace the `_PERFLINT_PREFIXES` prefix filter with an explicit
`_PERFLINT_HIGH_PRECISION` code allowlist (prefixes can't express the split — W8204 shares the W82
prefix with the dropped codes). Honesty updates to the leaf docstring + SKILL.md. Coordinated ship:
repo-A release → repo-B/repo-P re-pin + prune + reconverge.

**Tech Stack:** Python 3.14, perflint 0.8.1, pytest, the repo-A leaf-test convention
(`helpers.load_module()`). Spec:
`docs/superpowers/specs/2026-06-15-phase3-c2-perf-smell-narrowing-design.md`.

**Decision evidence (binding):** DROP trio W8201/W8202/W8205 = 49/77 family accepts, all `perflint-FP`
/ `non-hot-path`, **0 genuine fixes**; R8203 = Python<3.11, never fires. KEEP set
W8101/W8102/W8204/W8301/W8401/W8402/W8403 — W8301/W8401/W8402/W8403 had genuine fixes (repo-B
`wave_frozen.md`); W8101/W8102/W8204 are concrete deterministic checks.

---

## Task 1 — repo-A: narrow the leaf (TDD) + honesty updates

**Repo/branch:** `/home/jakub/projects/repo-audit-skills`, branch `feat/phase3-c2`.
**Files:**
- Modify: `skills/perf-smell-audit/scripts/perf_smell_audit.py`
- Modify: `skills/perf-smell-audit/SKILL.md`
- Create: `skills/perf-smell-audit/tests/test_perf_smell_precision.py`

- [ ] **Step 1: Write the failing precision tests**

Create `skills/perf-smell-audit/tests/test_perf_smell_precision.py`:

```python
"""Phase 3 C2: the leaf keeps only perflint's high-precision codes."""

from helpers import FIXTURES, load_module

ps = load_module()

KEEP = {"W8101", "W8102", "W8204", "W8301", "W8401", "W8402", "W8403"}
DROP = {"W8201", "W8202", "W8205", "R8203"}


def test_high_precision_set_keeps_concrete_drops_heuristics():
    assert KEEP <= ps._PERFLINT_HIGH_PRECISION
    assert ps._PERFLINT_HIGH_PRECISION.isdisjoint(DROP)
    # exactly the 7 keep codes, nothing else
    assert ps._PERFLINT_HIGH_PRECISION == KEEP


def test_dirty_fixture_drops_loop_invariant_keeps_container():
    # the dirty fixture triggers BOTH W8201 (loop-invariant, dropped) and
    # W8301 (use-tuple-over-list, kept).
    findings = ps.analyze_tree(FIXTURES / "dirty", source_prefixes=["pkg/"])
    codes = {f.metric_name for f in findings}
    assert "W8301" in codes          # kept high-precision code still detected
    assert "W8201" not in codes      # heuristic loop-invariant dropped
```

- [ ] **Step 2: Run, verify FAIL**

Run: `cd /home/jakub/projects/repo-audit-skills/skills/perf-smell-audit && python3 -m pytest tests/test_perf_smell_precision.py -q`
Expected: FAIL — `AttributeError: module 'perf_smell_audit' has no attribute '_PERFLINT_HIGH_PRECISION'`.

- [ ] **Step 3: Replace the prefix filter with the high-precision allowlist**

In `skills/perf-smell-audit/scripts/perf_smell_audit.py`, replace the block (lines ~19-22):

```python
# perflint reserves the 8xxx message range; we keep ONLY those ids. (`pylint
# --enable` takes message ids, not a plugin name, and pylint always emits its own
# fatals/syntax errors, which start with F/E and are dropped by this prefix filter.)
_PERFLINT_PREFIXES = ("W81", "W82", "W83", "W84", "R81", "R82")
```

with:

```python
# perflint's high-precision, deterministic message ids only. The loop-invariant
# checker's heuristic family is EXCLUDED — W8201 (loop-invariant-statement)
# over-approximates (flags loop-VARIANT expressions as invariant), and W8202
# (loop-global-usage) / W8205 (dotted-import-in-loop) are micro-opts in
# I/O-bound cold paths; together they produced 49 false-positive accepts
# family-wide with zero genuine fixes (Phase-3 C2). R8203 (loop-try-except) is
# Python <3.11 only. Kept: concrete container/cast/iterator checks (W8101,
# W8102), memoryview-over-bytes (W8204), and the deterministic list/comprehension
# refactors (W8301, W8401, W8402, W8403) — these caught genuine fixes.
_PERFLINT_HIGH_PRECISION = frozenset(
    {"W8101", "W8102", "W8204", "W8301", "W8401", "W8402", "W8403"}
)
```

- [ ] **Step 4: Update the filter call in `analyze_tree`**

In `analyze_tree`, change:

```python
        if not code.startswith(_PERFLINT_PREFIXES):
            # keep only perflint's own messages; drop pylint core + syntax errors
            continue
```

to:

```python
        if code not in _PERFLINT_HIGH_PRECISION:
            # keep only perflint's high-precision ids; drop heuristic + pylint core
            continue
```

- [ ] **Step 5: Update the module docstring (honesty)**

Replace the module docstring (lines 1-5):

```python
"""Static algorithmic-smell audit: wrap perflint (via pylint) → PERF findings.

Deterministic, advisory, never mutates source. High-precision subset only —
wrong-container, loop-invariant, and related performance anti-patterns.
"""
```

with:

```python
"""Static algorithmic-smell audit: wrap perflint (via pylint) → PERF findings.

Deterministic, advisory, never mutates source. High-precision subset only —
wrong-container, redundant-cast, dict-iterator, memoryview, and the
deterministic list/comprehension refactors. The loop-invariant-checker's
heuristic family (loop-invariant-statement, loop-global-usage,
dotted-import-in-loop) is excluded: it over-approximates and yields false
positives, not actionable signal.
"""
```

- [ ] **Step 6: Update SKILL.md description + Tools section (honesty)**

In `skills/perf-smell-audit/SKILL.md`:

(a) Replace the `description:` body lines:

```
  Deterministic, advisory algorithmic performance-smell audit for Python. Wraps
  perflint (via pylint) to emit PERF findings (loop-invariant computation, wrong
  container types, and related anti-patterns) to the shared code-health finding
  schema. Never mutates source.
```

with:

```
  Deterministic, advisory algorithmic performance-smell audit for Python. Wraps
  perflint (via pylint) to emit PERF findings for wrong container types, redundant
  casts, and list/comprehension refactors (perflint's high-precision deterministic
  checks) to the shared code-health finding schema. The over-approximating
  loop-invariant heuristics are excluded. Never mutates source.
```

(b) In the "Tools" section, replace the line:

```
perflint (via pylint, `--load-plugins=perflint`). Only perflint's own message ids
(the `W8*` / `R8*` range) are kept; pylint core, syntax, and import messages are
```

with:

```
perflint (via pylint, `--load-plugins=perflint`). Only perflint's high-precision
message ids are kept — W8101/W8102 (cast/iterator), W8204 (memoryview), W8301
(tuple-over-list), W8401/W8402/W8403 (comprehension refactors). The heuristic
loop-invariant family (W8201/W8202/W8205, R8203) is excluded; pylint core, syntax,
and import messages are
```

(Preserve whatever sentence continues after that line.)

- [ ] **Step 7: Run the precision tests + full leaf suite (green)**

Run: `cd /home/jakub/projects/repo-audit-skills/skills/perf-smell-audit && python3 -m pytest tests/ -q`
Expected: PASS — 8 passed (6 existing + 2 new). The existing `test_dirty_fixture_flags_perf_smells`
and `test_cli_dirty_exits_one_with_findings` still pass because the dirty fixture also triggers W8301.

- [ ] **Step 8: ruff clean**

Run: `cd /home/jakub/projects/repo-audit-skills && ~/.local/bin/ruff check skills/perf-smell-audit/scripts/perf_smell_audit.py`
Expected: `All checks passed!`

- [ ] **Step 9: Commit**

```bash
cd /home/jakub/projects/repo-audit-skills
git add skills/perf-smell-audit/scripts/perf_smell_audit.py \
        skills/perf-smell-audit/SKILL.md \
        skills/perf-smell-audit/tests/test_perf_smell_precision.py
git commit -m "feat(perf-smell): narrow to perflint high-precision codes

Drop the loop-invariant-checker heuristic trio (W8201 loop-invariant-statement,
W8202 loop-global-usage, W8205 dotted-import-in-loop) + dead R8203. These
produced 49 false-positive accepts family-wide with zero genuine fixes. Keep the
concrete checks (W8101/W8102/W8204) and the refactors that caught real fixes
(W8301/W8401/W8402/W8403). Honest docstring + SKILL.md scope update."
```

---

## Task 2 — repo-A: release bump v0.7.4 → v0.7.5

**Repo/branch:** `/home/jakub/projects/repo-audit-skills`, branch `feat/phase3-c2`.
**Files:** `package.json`, all 19 `skills/*/SKILL.md` (version line), `CHANGELOG.md`.

- [ ] **Step 1: Bump package.json** line 3 `"version": "0.7.4",` → `"version": "0.7.5",`.

- [ ] **Step 2: Bump all 19 leaf SKILL.md version strings**

```bash
cd /home/jakub/projects/repo-audit-skills
grep -rl '^version: 0.7.4$' skills/*/SKILL.md | xargs sed -i 's/^version: 0.7.4$/version: 0.7.5/'
grep -rl '^version: 0.7.5$' skills/*/SKILL.md | wc -l   # must print 19
grep -rl '^version: 0.7.4$' skills/*/SKILL.md           # must print nothing
```

- [ ] **Step 3: Prepend CHANGELOG entry** (under `# Changelog`, above `## 0.7.4`):

```markdown
## 0.7.5 - 2026-06-15

Phase 3 C2: narrowed `perf-smell-audit` to perflint's high-precision message ids. The
over-approximating loop-invariant-checker heuristics — W8201 (loop-invariant-statement, flags
loop-VARIANT expressions), W8202 (loop-global-usage), W8205 (dotted-import-in-loop) — plus the
Python<3.11-only R8203 are now excluded; they produced 49 false-positive accepts family-wide
(repo-B 29 + repo-P 20) with zero genuine fixes. The leaf keeps the concrete deterministic checks
(W8101 unnecessary-list-cast, W8102 incorrect-dictionary-iterator, W8204 memoryview-over-bytes) and
the list/comprehension refactors that caught real improvements (W8301, W8401, W8402, W8403).
Docstring + SKILL.md scope updated for honesty. perf-smell is a convergence-wave lane → repo-B/repo-P
re-pin their gate clone to v0.7.5 and prune the now-stale accepts.
```

- [ ] **Step 4: Verify** `node -e "console.log(require('./package.json').version)"` → 0.7.5;
  `grep -rl '^version: 0.7.5$' skills/*/SKILL.md | wc -l` → 19; `head -4 CHANGELOG.md` shows the entry.

- [ ] **Step 5: Commit**

```bash
cd /home/jakub/projects/repo-audit-skills
git add package.json skills/*/SKILL.md CHANGELOG.md
git commit -m "chore(release): family 0.7.4 -> 0.7.5 (Phase 3 C2 perf-smell high-precision narrowing)"
```

---

## (orchestrator) repo-A ship — NOT a subagent task

After Task 2: `npm run check` (expect only `growth` RED pre-tag); merge `feat/phase3-c2`→`main`
(no-ff); **tag v0.7.5**; confirm `python3 scripts/check_growth.py` → pass; push `main v0.7.5`
together; `gh release create v0.7.5`; reinstall leaves; **REAL CI green** (`gh run watch`, read JSON).
Read back bumps via `git show HEAD:<file>`. **v0.7.5 must be tagged+pushed before repo-B/repo-P CI.**

---

## Task 3 — repo-B: re-pin gate to v0.7.5 + prune 29 stale accepts

**Repo/branch:** `/home/jakub/projects/repo-audit-refactor-optimize`, branch `feat/phase3-c2`
(create it off `main` first: `git checkout main && git pull && git checkout -b feat/phase3-c2`).
**Files:** `.github/workflows/check.yml`, `.repo-audit/accept.json`.

- [ ] **Step 1: Re-pin the leaf clone** in `.github/workflows/check.yml` — change the single line
  `git clone --depth 1 --branch v0.7.2 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves`
  to `--branch v0.7.5`.

- [ ] **Step 2: Prune the 29 stale perf-smell accepts**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
python3 - <<'EOF'
import json, pathlib, collections
p = pathlib.Path(".repo-audit/accept.json")
d = json.loads(p.read_text())
DROP = {"W8201", "W8202", "W8205", "R8203"}
before = len(d["accept"])
removed = [it for it in d["accept"]
           if it.get("match", {}).get("leaf") == "perf-smell"
           and it["match"].get("metric") in DROP]
d["accept"] = [it for it in d["accept"]
               if not (it.get("match", {}).get("leaf") == "perf-smell"
                       and it["match"].get("metric") in DROP)]
assert len(removed) == 29, f"expected 29 removed, got {len(removed)}"
assert len(d["accept"]) == before - 29 == 36, len(d["accept"])
print("removed codes:", dict(collections.Counter(it['match']['metric'] for it in removed)))
p.write_text(json.dumps(d, indent=2) + "\n")
print(f"accept entries {before} -> {len(d['accept'])}")
EOF
```
Expected: `removed codes: {'W8201': 9, 'W8202': 12, 'W8205': 8}` (order may vary);
`accept entries 65 -> 36`.

- [ ] **Step 3: Confirm no W8201/W8202/W8205 perf-smell accepts remain**

```bash
python3 -c "import json; d=json.load(open('.repo-audit/accept.json')); ps=[x for x in d['accept'] if x.get('match',{}).get('leaf')=='perf-smell']; print('perf-smell accepts:', len(ps), 'codes:', sorted({x['match']['metric'] for x in ps}))"
```
Expected: `perf-smell accepts: 14 codes: ['W8301', 'W8402', 'W8403']`.

- [ ] **Step 4: Commit**

```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
git add .github/workflows/check.yml .repo-audit/accept.json
git commit -m "chore(gate): re-pin convergence leaves v0.7.2->v0.7.5 + prune 29 stale perf-smell accepts

perf-smell-audit narrowed in repo-A v0.7.5 (dropped loop-invariant heuristic trio
W8201/W8202/W8205). Those 29 accepts no longer match any finding -> pruned. The 14
W8301/W8402/W8403 accepts remain load-bearing under the narrowed leaf."
```

---

## (orchestrator) repo-B reconverge + ship — NOT a subagent task

After Task 3, the orchestrator runs the **decisive wave sim** with the NEW tag:
```bash
cd /home/jakub/projects/repo-audit-refactor-optimize
rm -rf /tmp/leaves && git clone --depth 1 --branch v0.7.5 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves
(cd /tmp/leaves && npm ci)
# pin-safety: only perf-smell-audit changed among wave leaves v0.7.2->v0.7.5
git clone --depth 1 --branch v0.7.2 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves072
diff -rq /tmp/leaves072/skills /tmp/leaves/skills   # expect ONLY perf-smell-audit (+ version lines)
PATH="/tmp/leaves/node_modules/.bin:$PATH" \
  SKILLS_ROOT=/tmp/leaves/skills WAVE_RUNNER=$(pwd)/scripts/run_diagnosis_wave.py \
  python3 scripts/check_wave_baseline.py        # read JSON: status pass, active 0, no stale
LEAF=/tmp/leaves/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  python3 scripts/check_coverage_gap.py --suite tests --source-prefix scripts   # exit 0
```
Then `python3 -m pytest tests/ -q` + `python3 scripts/check_release.py`; merge to `main`; push;
**REAL CI green** (convergence-gate wave + coverage-gap gate). No release.

---

## Task 4 — repo-P: re-pin gate to v0.7.5 + prune 20 stale accepts

**Repo/branch:** `/home/jakub/projects/perf-benchmark-skill`, branch `feat/phase3-c2` (off `main`).
**Files:** `.github/workflows/check.yml`, `.repo-audit/accept.json`.

- [ ] **Step 1: Re-pin the leaf clone** in `.github/workflows/check.yml` — change
  `git clone --depth 1 --branch v0.7.2 https://github.com/jc1122/repo-audit-skills.git /tmp/leaves`
  to `--branch v0.7.5`. **Leave the runner clone at `--branch v0.8.1`** (repo-B runner unchanged).

- [ ] **Step 2: Prune the 20 stale perf-smell accepts**

```bash
cd /home/jakub/projects/perf-benchmark-skill
python3 - <<'EOF'
import json, pathlib, collections
p = pathlib.Path(".repo-audit/accept.json")
d = json.loads(p.read_text())
DROP = {"W8201", "W8202", "W8205", "R8203"}
before = len(d["accept"])
removed = [it for it in d["accept"]
           if it.get("match", {}).get("leaf") == "perf-smell"
           and it["match"].get("metric") in DROP]
d["accept"] = [it for it in d["accept"]
               if not (it.get("match", {}).get("leaf") == "perf-smell"
                       and it["match"].get("metric") in DROP)]
assert len(removed) == 20, f"expected 20 removed, got {len(removed)}"
assert len(d["accept"]) == before - 20 == 40, len(d["accept"])
print("removed codes:", dict(collections.Counter(it['match']['metric'] for it in removed)))
p.write_text(json.dumps(d, indent=2) + "\n")
print(f"accept entries {before} -> {len(d['accept'])}")
EOF
```
Expected: `removed codes: {'W8201': 8, 'W8202': 7, 'W8205': 5}`; `accept entries 60 -> 40`.

- [ ] **Step 3: Confirm remaining perf-smell accepts**

```bash
python3 -c "import json; d=json.load(open('.repo-audit/accept.json')); ps=[x for x in d['accept'] if x.get('match',{}).get('leaf')=='perf-smell']; print('perf-smell accepts:', len(ps), 'codes:', sorted({x['match']['metric'] for x in ps}))"
```
Expected: `perf-smell accepts: 14 codes: ['W8301', 'W8401', 'W8402', 'W8403']`.

- [ ] **Step 4: ruff (repo-P CI runs standalone ruff)**

```bash
cd /home/jakub/projects/perf-benchmark-skill
~/.local/bin/ruff check scripts/ tests/ && ~/.local/bin/ruff format --check scripts/ tests/
```
Expected: clean (this change only edits YAML + JSON, but run anyway per the repo-P guardrail).

- [ ] **Step 5: Commit**

```bash
cd /home/jakub/projects/perf-benchmark-skill
git add .github/workflows/check.yml .repo-audit/accept.json
git commit -m "chore(gate): re-pin convergence leaves v0.7.2->v0.7.5 + prune 20 stale perf-smell accepts

perf-smell-audit narrowed in repo-A v0.7.5 (dropped loop-invariant heuristic trio).
Those 20 accepts no longer match -> pruned. Runner pin stays v0.8.1 (unchanged)."
```

---

## (orchestrator) repo-P reconverge + ship — NOT a subagent task

Same decisive wave sim as repo-B but with the subprocess-capture coverage-gap invocation:
```bash
cd /home/jakub/projects/perf-benchmark-skill
rm -rf /tmp/leavesP && git clone --depth 1 --branch v0.7.5 https://github.com/jc1122/repo-audit-skills.git /tmp/leavesP
(cd /tmp/leavesP && npm ci)
rm -rf /tmp/runnerP && git clone --depth 1 --branch v0.8.1 https://github.com/jc1122/repo-audit-refactor-optimize.git /tmp/runnerP
PATH="/tmp/leavesP/node_modules/.bin:$PATH" \
  SKILLS_ROOT=/tmp/leavesP/skills WAVE_RUNNER=/tmp/runnerP/scripts/run_diagnosis_wave.py \
  python3 scripts/check_wave_baseline.py        # JSON: status pass, active 0, no stale
LEAF=/tmp/leavesP/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  python3 scripts/check_coverage_gap.py --subprocess-capture \
    --suite tests --suite perf-optimization/tests \
    --source-prefix scripts --source-prefix perf-optimization/scripts   # exit 0
```
Then `python3 -m pytest tests/ -q`; merge to `main`; push; **REAL CI green**. No release.

---

## Self-review notes

- **Spec coverage:** allowlist (spec §Design) → T1 S3-S4; honesty docstring/SKILL.md (spec §Design) →
  T1 S5-S6; tests (spec §Tests) → T1 S1; repo-A v0.7.5 (spec §ship 1) → T2 + orchestrator; repo-B
  re-pin+prune 29 (spec §ship 2) → T3; repo-P re-pin+prune 20, keep runner (spec §ship 3) → T4;
  pin-safety diff (spec §pin-safety) → repo-B orchestrator block. All covered.
- **Placeholder scan:** none.
- **Type consistency:** `_PERFLINT_HIGH_PRECISION` (frozenset of codes) used identically in the leaf,
  the comment, and the test; the prune filter `match.leaf=="perf-smell" and match.metric in DROP` is
  identical in T3/T4 and verified against the measured counts (29 / 20).
