# Phase 3 · C3 — mutation-convention pilot (coverage-gap-audit) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** Migrate ONE repo-A leaf's tests (coverage-gap-audit) from `spec_from_file_location` to a
normal top-level import so it becomes mutmut-correlatable, keep it green, and (with the in-session
mutation measurement already captured) record the STOP-on-expansion decision.

**Architecture:** Test-only change to `skills/coverage-gap-audit/tests/helpers.py`. The in-process
test (`test_coverage_gap_findings.py`) loads the module via `load_module()`; switching that loader to
`import coverage_gap_audit` (leaf `scripts/` on `sys.path`) removes the trampoline blocker. No
release. Spec: `docs/superpowers/specs/2026-06-15-phase3-c3-mutation-convention-pilot-design.md`.

**Tech Stack:** Python 3.14, pytest, mutmut 3.6.0 (already measured), repo-A leaf-test convention.

**Decision (binding, from the spec):** the measured kill rate (0.392) is an artifact — 168/211
mutants are "no tests" false survivors in CLI/main code covered only by the leaf's *subprocess* tests
(mutmut can't instrument subprocess); the in-process survivors are mostly equivalents. Feasibility is
proven but full migration is NOT justified → **STOP on expansion**, mutation stays Tier-2 advisory.

---

## Task 1 — repo-A: migrate coverage-gap-audit's `helpers.load_module()` to a normal import

**Repo/branch:** `/home/jakub/projects/repo-audit-skills`, branch `feat/phase3-c3`.
**Files:** Modify `skills/coverage-gap-audit/tests/helpers.py`.

- [ ] **Step 1: Confirm the current leaf suite is green (baseline)**

Run: `cd /home/jakub/projects/repo-audit-skills/skills/coverage-gap-audit && python3 -m pytest tests/ -q`
Expected: 13 passed.

- [ ] **Step 2: Rewrite `tests/helpers.py` to use a normal top-level import (net ≤ 0 LOC)**

Replace the entire contents of `skills/coverage-gap-audit/tests/helpers.py` with the following
(**26 lines, same as the original — net LOC ≤ 0** so repo-A's growth gate stays green without a
release; the full rationale lives in `c3-evidence`, only a terse pointer comment here):

```python
import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "coverage_gap_audit.py"
FIXTURES = SKILL_ROOT / "tests" / "fixtures"

# C3 pilot: normal import (not spec_from_file) for mutmut — see c3-evidence
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def load_module():
    import coverage_gap_audit

    return coverage_gap_audit


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=False
    )


def read_findings(out_dir):
    return json.loads((Path(out_dir) / "coverage-gap_findings.json").read_text())
```

(The only behavioral change is `load_module`: `spec_from_file_location` → top-level
`import coverage_gap_audit` with the leaf `scripts/` on `sys.path`. `importlib.util` is dropped;
`run_cli`/`read_findings`/`FIXTURES`/`SCRIPT` are preserved. Top-level import — NOT
`import scripts.coverage_gap_audit`, which would collide with repo-A's own top-level `scripts/` when
the coverage gate runs each suite with `cwd=<repo-A root>`.)

- [ ] **Step 3: Run the leaf suite (still green)**

Run: `cd /home/jakub/projects/repo-audit-skills/skills/coverage-gap-audit && python3 -m pytest tests/ -q`
Expected: 13 passed.

- [ ] **Step 4: Run the leaf suite GATE-STYLE (cwd = repo-A root) — proves no `scripts/` collision**

Run: `cd /home/jakub/projects/repo-audit-skills && python3 -m pytest skills/coverage-gap-audit/tests -q`
Expected: 13 passed (confirms `import coverage_gap_audit` resolves to the leaf, not repo-A's
gate `scripts/`, when cwd is the repo root — exactly how the coverage gate runs each suite).

- [ ] **Step 5: ruff clean**

Run: `cd /home/jakub/projects/repo-audit-skills && ~/.local/bin/ruff check skills/coverage-gap-audit/tests/helpers.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd /home/jakub/projects/repo-audit-skills
git add skills/coverage-gap-audit/tests/helpers.py
git commit -m "test(coverage-gap-audit): C3 pilot — migrate load_module to a normal import

Phase-3 C3 pilot: switch this leaf's in-process test loader from
spec_from_file_location to a normal top-level \`import coverage_gap_audit\`
(leaf scripts/ on sys.path), removing mutmut 3.x's trampoline blocker. Top-level
import is required (scripts.X collides with repo-A's own scripts/ at cwd=root).
Test-only, leaf suite green. The other 96 files keep the convention (C3 decision:
STOP — mutation can't credit the family's subprocess CLI tests)."
```

---

## (orchestrator) repo-A verify + land — NOT a subagent task

1. `npm run check` — confirm **all gates green** (C3 ships no tag, so growth must be GREEN). The
   rewrite is **net ≤ 0 LOC** (drops `importlib.util` + the 4-line spec body; adds a 1-line comment +
   sys.path + 2-line loader → net ≈ −1), so `net_loc_growth` (additions − deletions) stays ≤ 0 →
   growth `count 0`. The coverage gate re-runs this leaf's suite (still green). Read the growth JSON
   to confirm `count 0` before merging.
2. Merge `feat/phase3-c3` → repo-A `main` (no-ff); push. **No tag, no release.**
3. Verify repo-A REAL CI green (`gh run watch`, read gate JSON) incl. coverage-gap gate.
4. repo-B/repo-P: untouched (they clone the leaf *script*, not its tests) — confirm still green.

---

## (orchestrator) measurement evidence + decision — NOT a subagent task

1. Re-run the mutation measurement against the migrated leaf via the documented staging recipe (module
   + `health_common.py` under `scripts/`, import-key-aligned, `test-effectiveness-audit
   --source-prefix scripts --max-mutants 800`) and save the findings JSON to
   `repo-B docs/superpowers/c3-evidence/coverage-gap-mutation.json`.
2. Write `repo-B docs/superpowers/c3-evidence/outcome.md` (kill rate 0.392, survivor breakdown,
   feasibility-proven + STOP-on-expansion decision).
3. Commit spec + plan + evidence to repo-B (merge `feat/phase3-c3` → main).

---

## Self-review notes

- **Spec coverage:** migration (spec §Pilot design) → T1 S2; top-level-import rationale (spec) → T1
  S4 gate-style check; measurement (spec §Measurement) → orchestrator measurement step; STOP decision
  (spec §Decision) → evidence step; test-only no-release (spec §Ship) → orchestrator land step. All
  covered.
- **Placeholder scan:** none.
- **Growth:** C3 ships no tag, so repo-A growth must be GREEN. The 26-line rewrite (== original line
  count, net ≈ −1) keeps `net_loc_growth` ≤ 0 → growth `count 0`. Verified in the orchestrator step.
