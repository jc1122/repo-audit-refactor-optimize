# Phase 3 · C2 — outcome (VERIFIED WIN, coordinated; repo-A v0.7.5 + repo-B/repo-P re-pin & prune)

Completed 2026-06-15. `perf-smell-audit` narrowed to perflint's high-precision subset; the
convergence wave re-pinned to v0.7.5 and the 49 false-positive perf-smell accepts pruned family-wide.
Full superpowers pipeline: spec
(`specs/2026-06-15-phase3-c2-perf-smell-narrowing-design.md`) → plan
(`plans/2026-06-15-phase3-c2-perf-smell-narrowing.md`) → subagent-driven-development (fresh implementer
per task + spec-then-quality review on the leaf change).

## Measure-then-decide (the decisive evidence)

perflint 0.8.1 = 11 codes. **All 77 family accepts came from 7 codes.** Git-history triage:
- repo-P convergence commit `46409d9`: *"No source code changes needed"* — all 34 findings FP /
  non-hot-path / cant-fix.
- repo-B `scripts/wave_frozen.md`: **genuine fixes applied** for W8301 (use-tuple-over-list), W8401
  (use-list-comprehension), W8402 (use-list-copy via extend+genexp), W8403 (use-dict-comprehension).

→ The **loop-invariant-checker heuristic trio W8201/W8202/W8205** (49/77 accepts: repo-B 29, repo-P
20) had **zero genuine fixes** — every accept reason `perflint-FP` (over-approximation) or
`non-hot-path`. **R8203** (loop-try-except) is Python <3.11 only → never fires on the family (3.14).
The KEEP codes either caught genuine fixes (W8301/W8401/W8402/W8403) or are perflint's concrete
deterministic checks (W8101 unnecessary-list-cast / W8102 incorrect-dictionary-iterator / W8204
memoryview-over-bytes, 0 findings). **Decision: narrow** — precision materially improves (−49 FP
accepts, 64 %) without losing any code that ever caught a real improvement.

## Change

- repo-A leaf: `_PERFLINT_PREFIXES` (prefix tuple) → `_PERFLINT_HIGH_PRECISION = frozenset({W8101,
  W8102, W8204, W8301, W8401, W8402, W8403})`; filter `code not in _PERFLINT_HIGH_PRECISION`. (Exact
  code allowlist needed — W8204 is high-precision but shares the W82 prefix with the dropped codes.)
- Honesty: module docstring + SKILL.md `description`/`Tools`/`Limits` updated to drop "loop-invariant
  computation" and state the exclusion (a code-quality-review catch).
- Tests: `tests/test_perf_smell_precision.py` (set partition + end-to-end dirty-fixture proof that
  W8201 is dropped, W8301 kept, C0114 pylint-core noise dropped); dirty-fixture line marked
  load-bearing. Leaf suite 6 → 8 passed.

## Coordinated ship (perf-smell IS a wave lane) — order repo-A → repo-B → repo-P

| repo | change | version | REAL CI |
|------|--------|---------|---------|
| repo-A | narrowed leaf + honest SKILL.md + tests; family bump | **v0.7.5** (merge `baa5209`, tagged, released, reinstalled) | run 27518507643 ✅ (growth re-baselined v0.7.5, selfaudit, coverage-gap) |
| repo-B | re-pin `check.yml` clone v0.7.2→v0.7.5; **prune 29** accepts (W8201×9/W8202×12/W8205×8); 65→36 | no release (gate+ledger) | run 27518673314 ✅ **convergence-gate + coverage-gap green** (merge `7df332d`) |
| repo-P | re-pin clone v0.7.2→v0.7.5 (runner stays v0.8.1); **prune 20** accepts (W8201×8/W8202×7/W8205×5); 60→40 | no release | run 27518757465 ✅ both jobs (convergence-gate cloned v0.7.5 + coverage-gap subprocess-capture) (merge `b9e835e`) |

## Decisive pre-push checks (orchestrator-run, not worker "green")

- **Pin-safety diff** v0.7.2 vs v0.7.5: only `perf-smell-audit` (wave lane) and `test-audit-pipeline`
  (NOT a wave lane, C1) leaf *scripts* changed → the wave's only behavioral change is the perf-smell
  narrowing; coverage-gap-audit leaf unchanged.
- **repo-B wave sim** (`/tmp/leaves@v0.7.5`): `status pass, active 0`, no stale (perf-smell 24 raw →
  14 KEEP unique keys, all accepted). coverage-gap sim `pass count 0`. 317 tests, release-check pass.
- **repo-P wave sim** (`/tmp/leavesP@v0.7.5` + `/tmp/runnerP@v0.8.1`): `status pass, active 0`, no
  stale (perf-smell 19 raw → 14 KEEP). coverage-gap subprocess-capture `pass count 0`. 124 tests,
  ruff clean.

## Result

**Family perf-smell accepts 77 → 28** (−49 false positives, −64 %). The leaf now reports only
high-precision, deterministic perf smells; the over-approximating loop-invariant heuristics no longer
flood the wave with FPs requiring accept entries. All 3 mains CI-green incl convergence-gate +
coverage-gap gate.

## Status: TERMINAL — verified win. repo-A v0.7.5 shipped; repo-B/repo-P re-pinned+pruned+reconverged.
