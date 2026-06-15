# Phase 3 · C3 — outcome (PILOT done; feasibility PROVEN, expansion STOPPED — honest no-win)

Completed 2026-06-15. Pilot-migrated ONE repo-A leaf (`coverage-gap-audit`) from
`spec_from_file_location` to a normal import, measured native mutation testing, and decided **not** to
expand to the other 96 files. Full superpowers pipeline: spec
(`specs/2026-06-15-phase3-c3-mutation-convention-pilot-design.md`) → plan
(`plans/2026-06-15-phase3-c3-mutation-convention-pilot.md`) → subagent-driven-development (implementer
+ spec review) → in-session measurement.

## Problem (B3)

repo-A's 97 leaf-test files load modules via `helpers.load_module()` /
`spec_from_file_location`, which bypasses mutmut 3.x's trampoline → repo-A was "not mutation-testable
at all" (B3 `repoA-blocked.md`).

## Pilot migration (shipped, test-only, no release)

`skills/coverage-gap-audit/tests/helpers.py` `load_module()`: `spec_from_file_location` → top-level
`import coverage_gap_audit` (leaf `scripts/` on `sys.path`). **Top-level import is required** — `import
scripts.coverage_gap_audit` would collide with repo-A's own top-level `scripts/` because the coverage
gate runs each leaf suite as a separate `pytest <suite>` subprocess with `cwd=<repo-A root>`. Verified
green **13 passed** both normally and gate-style (`cwd=<repo-A root>`); net **0** LOC (5/5 numstat) so
repo-A's growth gate stays green with **no release**. Merged to repo-A `main` (`38469f2`), REAL CI
green incl. coverage-gap gate. repo-B/repo-P untouched (they clone the leaf *script*, not its tests).

## Measurement (`test-effectiveness-audit` / mutmut 3.6.0)

Staged the migrated leaf (module + vendored `health_common.py` under `scripts/`, import-key-aligned)
and ran mutation. Artifacts: `coverage-gap-mutation-findings.json`, `survivor-breakdown.txt`.

**`scripts/coverage_gap_audit.py` kill rate = 0.392** (211 mutants). Breakdown:

| function | count | mutmut status | reality |
|---|---|---|---|
| build_parser | 72 | **no tests** | covered by subprocess `test_coverage_gap_cli` — invisible to mutmut |
| main | 67 | **no tests** | covered by subprocess CLI tests — invisible to mutmut |
| render_report | 21 | **no tests** | covered by subprocess CLI tests — invisible to mutmut |
| load_thresholds | 8 | **no tests** | covered by subprocess CLI tests — invisible to mutmut |
| analyze_tree | 22 | survived | in-process-tested; mix of equivalents + minor branches |
| load_coverage | 14 | survived | incl. equivalents (`encoding="utf-8"→None`, identical on Linux) |
| _coverage_percent | 5 | survived | incl. ONE genuine trivial edge case (`statements==0→1`) |
| _rel / _iter_python_files | 2 | survived | minor |

**168 / 211 (80 %) are "no tests" false survivors** in CLI/main/argparse/report code that the leaf's
**subprocess** tests cover thoroughly — mutmut cannot instrument subprocess execution. The 43 genuine
in-process survivors are dominated by **equivalents** (matching B3's repo-B finding) plus a couple of
trivial edge cases. No high-value gap surfaced.

## Decision: STOP — do not migrate the other 96 files (honest no-win on full migration)

1. **Feasibility PROVEN:** the convention migration removes the `spec_from_file` trampoline blocker —
   mutmut now runs on a repo-A leaf and yields a real kill rate. B3's "repo-A not mutation-testable"
   is *unblockable* by this migration.
2. **Value NOT justified:** the kill rate is fundamentally untrustworthy for this family because
   mutmut credits only in-process tests, while every leaf deliberately splits testing into
   in-process-logic tests + **subprocess-CLI tests** (the same architecture B1 needed
   `subprocess-capture` coverage to credit). mutmut has **no subprocess-capture equivalent** → ~80 %
   of each leaf's mutants (all CLI/main code) are "no tests" though thoroughly tested, and the genuine
   in-process survivors are mostly equivalents. Migrating 96 more files (plus per-leaf `health_common`
   sibling-staging + import-key-alignment complexity) would be high churn for a metric that
   **systematically understates** the suite and surfaces no real gaps.

**Therefore:** keep the `spec_from_file_location` convention (testability-without-packaging outweighs
mutation coverage), land the pilot leaf as the documented reference, and **keep the mutation lane
Tier-2 advisory** (confirms B3/B4). The one genuine trivial survivor (`_coverage_percent`
`statements==0`) is **not** chased — closing an advisory metric's edge case is the rubric-chasing
churn B3 explicitly declined.

## Status: TERMINAL — pilot migrated + green on repo-A main; mutation report committed; STOP decision recorded; repo-A CI-green; repo-B/repo-P untouched + green.
