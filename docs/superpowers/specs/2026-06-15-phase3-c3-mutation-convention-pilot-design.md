# Phase 3 · C3 — repo-A mutation-testability: convention-migration PILOT (one leaf, then decide)

**Date:** 2026-06-15
**Item:** Phase-3 C3 (see `docs/superpowers/PHASE3-LAUNCH-PROMPT.md` §C3; B3
`report.md`/`repoA-blocked.md`).
**Repo touched:** repo-A `repo-audit-skills` (`skills/coverage-gap-audit/tests/`) — **test-only →
NO release**. Evidence in repo-B `docs/superpowers/c3-evidence/`.

## Problem (B3)

repo-A's leaf tests load modules via `helpers.load_module()` /
`importlib.util.spec_from_file_location` (**97 test files**). mutmut 3.x instruments source through a
runtime trampoline that `spec_from_file_location` bypasses → no repo-A module is natively
mutation-testable (B3's `repoA-blocked.md`). C3 is a **pilot**: migrate ONE leaf's tests to a normal
import, measure whether native mutation testing surfaces genuine gaps, then **decide** whether to
migrate the other 96 files.

## Pilot design (coverage-gap-audit leaf)

The leaf has 4 test files: `test_coverage_gap_findings.py` (in-process, via `load_module()`) and
`test_coverage_gap_cli.py` / `_relpaths.py` / `_idempotent.py` (subprocess via `run_cli`). Only the
in-process file can correlate with mutmut.

**Migration** (`tests/helpers.py`): replace the `spec_from_file_location` loader with a normal
top-level import after putting the leaf's `scripts/` on `sys.path`:

```python
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

def load_module():
    import coverage_gap_audit       # normal import — mutmut-compatible
    return coverage_gap_audit
```

**Why top-level `import coverage_gap_audit`, not `import scripts.coverage_gap_audit`:** repo-A's
*own* root has a top-level `scripts/` dir, and the coverage gate runs each leaf suite as a separate
`pytest <suite>` subprocess with `cwd=<repo-A root>`. So `import scripts.coverage_gap_audit` would
resolve to (and collide with) repo-A's gate `scripts/`. The top-level form (leaf `scripts/` on
`sys.path`) is the only one that works standalone — and it matches mutmut's mutant key when the module
is mutated as a top-level source. (Verified: migrated leaf suite **13 passed** run gate-style with
`cwd=<repo-A root>`.)

This preserves standalone testability with **no packaging**. The other 3 (subprocess) files are
unchanged — they don't import the module in-process.

## Measurement (done in-session; recipe + result committed to evidence)

Staged the migrated leaf in `/tmp` (module + its vendored `health_common.py` sibling under `scripts/`
+ the in-process test, import-key-aligned to `scripts.coverage_gap_audit` as a throwaway measurement
harness) and ran `test-effectiveness-audit` (mutmut 3.6.0):

**`scripts/coverage_gap_audit.py` kill rate = 0.392** (211 mutants). Survivor breakdown:

| function | count | mutmut status | reality |
|---|---|---|---|
| build_parser | 72 | **no tests** | tested by subprocess `test_coverage_gap_cli` — invisible to mutmut |
| main | 67 | **no tests** | tested by subprocess CLI tests — invisible to mutmut |
| render_report | 21 | **no tests** | tested by subprocess CLI tests — invisible to mutmut |
| load_thresholds | 8 | **no tests** | tested by subprocess CLI tests — invisible to mutmut |
| analyze_tree | 22 | survived | in-process-tested; mix of equivalents + minor branches |
| load_coverage | 14 | survived | incl. equivalents (e.g. `encoding="utf-8"→None`, identical on Linux) |
| _coverage_percent | 5 | survived | incl. one genuine trivial edge case (`statements==0→1`) |
| _rel / _iter_python_files | 2 | survived | minor |

**168 / 211 (80 %) of mutants are "no tests" false survivors** in CLI/main/argparse/report code that
the leaf's **subprocess** tests cover thoroughly — mutmut cannot instrument subprocess execution. The
43 genuinely in-process survivors are dominated by equivalents (matching B3's repo-B finding) plus a
couple of trivial edge cases. No high-value gap surfaced.

## Decision: STOP — do not expand to the other 96 files (honest no-win on full migration)

The pilot delivered two findings:

1. **Feasibility: PROVEN.** The convention migration removes the `spec_from_file` trampoline blocker —
   mutmut runs and yields a real kill rate. B3's "repo-A is not mutation-testable at all" is
   *unblockable* by this migration.
2. **Value: NOT justified.** The kill rate is **fundamentally untrustworthy for this family** because
   mutmut credits only in-process tests, and every leaf deliberately splits testing into
   in-process-logic tests + subprocess-CLI tests (the same architecture B1 needed `subprocess-capture`
   coverage to credit). mutmut has **no subprocess-capture equivalent**, so it marks ~80 % of each
   leaf's mutants (all CLI/main code) as "no tests" though they are thoroughly tested — and the
   genuine in-process survivors are mostly equivalents. Migrating 96 more files (plus the per-leaf
   `health_common` sibling-staging and import-key-alignment complexity) would be high churn for a
   metric that **systematically understates** the suite and surfaces no real gaps.

**Therefore: keep the `spec_from_file_location`/`helpers.load_module` convention** (its
testability-without-packaging benefit outweighs mutation coverage), land the **pilot leaf** as the
documented reference, and **keep the mutation lane Tier-2 advisory** (confirms B3/B4). The genuine
trivial edge case (`_coverage_percent` `statements==0`) is **not** chased — closing an advisory
metric's edge case is the rubric-chasing churn B3 explicitly declined.

## Ship (test-only → NO release)

- repo-A `feat/phase3-c3`: migrate `skills/coverage-gap-audit/tests/helpers.py` (+ a one-line comment
  marking it the C3 pilot reference). All 4 test files stay green. Merge to repo-A `main`. **No
  version bump, no tag, no release** (no SKILL.md / leaf-behaviour change; L13). repo-B/repo-P
  unaffected (they clone the leaf *script*, not its tests; pins stay v0.7.5).
- repo-B `feat/phase3-c3`: spec + plan + `c3-evidence/` (the mutation findings JSON + this decision).

## Falsifiable DONE

- coverage-gap-audit tests migrated to normal import + **green** (leaf suite + repo-A `npm run check`
  incl. coverage-gap gate).
- A mutation report for the leaf committed (`c3-evidence/`).
- The expand-or-stop decision (**STOP**) recorded with evidence.
- repo-A CI-green; repo-B/repo-P untouched + green.

## Non-goals

- Not migrating the other 96 test files (the decision is STOP).
- Not closing the trivial `_coverage_percent` edge case (advisory rubric-chasing).
- No release; no gate/pin change.
