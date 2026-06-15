# Phase 3 · C2 — narrow `perf-smell-audit` to its high-precision subset (coordinated)

**Date:** 2026-06-15
**Item:** Phase-3 C2 (see `docs/superpowers/PHASE3-LAUNCH-PROMPT.md` §C2; B0 deferral + repo-A
`SP15-CANDIDATES.md`).
**Repos touched:** repo-A `repo-audit-skills` (leaf + SKILL.md → **release v0.7.5**), repo-B
`repo-audit-refactor-optimize` (re-pin gate + prune accepts, **no release**), repo-P
`perf-benchmark-skill` (re-pin gate + prune accepts, **no release**).

## Problem

`skills/perf-smell-audit/scripts/perf_smell_audit.py` keeps the **whole** perflint message range via
`_PERFLINT_PREFIXES = ("W81","W82","W83","W84","R81","R82")` — an over-approximation. The leaf's own
docstring already *claims* "High-precision subset only", and its SKILL.md advertises "loop-invariant
computation" — but the kept range includes perflint's heuristic loop-invariant family, which
over-approximates. This produced **77 family-wide perf-smell accepts** (repo-B 43 + repo-P 34 in
`.repo-audit/accept.json`) papering over false positives.

## Measurement (measure-then-decide — the decisive evidence)

perflint 0.8.1 has **11** message ids across 4 checkers:

| checker | code | symbol | nature |
|---|---|---|---|
| for-loop-checker | W8101 | unnecessary-list-cast | concrete / deterministic |
| for-loop-checker | W8102 | incorrect-dictionary-iterator | concrete / deterministic |
| loop-invariant-checker | **W8201** | loop-invariant-statement | **heuristic — over-approximates** |
| loop-invariant-checker | **W8202** | loop-global-usage | **heuristic micro-opt** |
| loop-invariant-checker | **R8203** | loop-try-except-usage | **Python <3.11 only (dead on 3.14)** |
| loop-invariant-checker | W8204 | memoryview-over-bytes | concrete / deterministic |
| loop-invariant-checker | **W8205** | dotted-import-in-loop | **heuristic micro-opt** |
| list-checker | W8301 | use-tuple-over-list | concrete refactor |
| comprehension-checker | W8401 | use-list-comprehension | concrete refactor |
| comprehension-checker | W8402 | use-list-copy | concrete refactor |
| comprehension-checker | W8403 | use-dict-comprehension | concrete refactor |

**Family accept distribution by code** (all 77 come from 7 codes):

| code | repo-B | repo-P | total | verdict |
|---|---|---|---|---|
| W8201 loop-invariant-statement | 9 | 8 | **17** | **DROP** |
| W8202 loop-global-usage | 12 | 7 | **19** | **DROP** |
| W8205 dotted-import-in-loop | 8 | 5 | **13** | **DROP** |
| W8301 use-tuple-over-list | 12 | 6 | 18 | KEEP |
| W8401 use-list-comprehension | 0 | 3 | 3 | KEEP |
| W8402 use-list-copy | 1 | 2 | 3 | KEEP |
| W8403 use-dict-comprehension | 1 | 3 | 4 | KEEP |

**True-signal evidence (git history):**
- repo-P's convergence commit `46409d9` message: *"No source code changes needed"* — all 34 findings
  triaged as `perflint-FP` / `non-hot-path` / `cant-fix`.
- repo-B's `scripts/wave_frozen.md` ("perf-smell lane integration") documents **genuine fixes
  applied**: dict-comprehension in `load_lanes` (W8403), tuples in `_leaf_supports_exclude_prefix` /
  `validate_run_report` / `load_source_overrides` (W8301), list-comprehensions in
  `_relevant_lane_names` / `_parse_version` (W8401), `extend`+genexp in `_markdown_report` (W8402).
- The accept reasons for the DROP trio are uniformly `perflint-FP` (e.g. W8201 *"fires on
  `manifest[lanes][lane_name]` — loop-VARIANT, perflint over-approximates the outer dict access"*) or
  `non-hot-path` (W8202/W8205 micro-opts in I/O-bound cold paths). **Zero genuine fixes** for the
  DROP trio. R8203 is gated to Python <3.11 and **never fires** on the family (3.14) — dead.

**Conclusion:** the loop-invariant-checker's heuristic trio (**W8201, W8202, W8205**) plus the dead
**R8203** account for **49/77 (64 %)** of the perf-smell accepts with **0 genuine fixes** — pure
false positives. The other 7 codes either caught **genuine fixes** (W8301/W8401/W8402/W8403) or are
perflint's concrete, deterministic checks with no false positives in the family (W8101/W8102/W8204).
Narrowing to the 7 high-precision codes **materially improves precision (−49 FP accepts) without
losing any code that ever caught a real improvement** → satisfies the ship condition.

## Design

### Leaf change (repo-A)

Replace the prefix tuple with an explicit high-precision **code allowlist** (prefixes can't express
the split — W8204 is high-precision but shares the `W82` prefix with the dropped W8201/W8202/W8205):

```python
# perflint's high-precision, deterministic message ids. The loop-invariant-
# checker's heuristic family (W8201 loop-invariant-statement, W8202
# loop-global-usage, W8205 dotted-import-in-loop) is EXCLUDED — it
# over-approximates (loop-variant expressions flagged as invariant; micro-opts
# in I/O-bound cold paths) and produced 49 false-positive accepts family-wide
# with zero genuine fixes (Phase-3 C2). R8203 (loop-try-except) is Python <3.11
# only. W8204 (memoryview-over-bytes) is kept — concrete and deterministic.
_PERFLINT_HIGH_PRECISION = frozenset(
    {"W8101", "W8102", "W8204", "W8301", "W8401", "W8402", "W8403"}
)
```

Filter change in `analyze_tree`: `if not code.startswith(_PERFLINT_PREFIXES):` →
`if code not in _PERFLINT_HIGH_PRECISION:`.

**Honesty updates** (the leaf no longer detects loop-invariant computation):
- Module docstring: drop "loop-invariant"; state the high-precision scope + the exclusion.
- The inline `_PERFLINT_PREFIXES` comment is replaced by the allowlist comment above.
- SKILL.md `description`: replace "loop-invariant computation, wrong container types, and related
  anti-patterns" with "wrong container types, redundant casts, and comprehension-rewrite
  opportunities (perflint's high-precision deterministic checks; the over-approximating loop-invariant
  heuristics are excluded)".
- SKILL.md "Tools" section: replace "Only perflint's own message ids (the `W8*` / `R8*` range) are
  kept" with the explicit high-precision id list + the exclusion note.

### Tests (TDD, existing leaf convention `helpers.load_module()`)

The `dirty` fixture triggers **both** W8201 (drop) and W8301 (keep), so existing
`test_dirty_fixture_flags_perf_smells` / `test_cli_dirty_exits_one_with_findings` still pass
(W8301 remains). Add a focused module `tests/test_perf_smell_precision.py`:

1. `test_high_precision_set` — the 7 keep codes ∈ `_PERFLINT_HIGH_PRECISION`; W8201/W8202/W8205/R8203
   ∉ it.
2. `test_dirty_fixture_drops_loop_invariant_keeps_container` — `analyze_tree(dirty)` metric names
   **contain W8301** and **do not contain W8201** (end-to-end proof the drop takes effect).

### Coordinated ship (perf-smell IS a wave lane → behaviour changed)

**Order repo-A → repo-B → repo-P.**

1. **repo-A** (`feat/phase3-c2`): narrow leaf + SKILL.md + tests; bump `package.json` 0.7.4→**0.7.5**
   + **all 19** leaf SKILL.md + dated CHANGELOG (2026-06-15); `npm run check` (only growth RED
   pre-tag); merge; **tag v0.7.5**; confirm growth green; `gh release create v0.7.5`; reinstall;
   REAL CI green.
2. **repo-B** (`feat/phase3-c2`): re-pin `.github/workflows/check.yml` clone `--branch v0.7.2 →
   v0.7.5` (one line); **prune the 29 stale accepts** (W8201×9, W8202×12, W8205×8) from
   `.repo-audit/accept.json`; reconverge. **Decisive pre-push sim:** re-clone `/tmp/leaves` at
   **v0.7.5**, `npm ci`, PATH-prepend jscpd, run `SKILLS_ROOT=/tmp/leaves/skills WAVE_RUNNER=$(pwd)/
   scripts/run_diagnosis_wave.py python3 scripts/check_wave_baseline.py` → JSON `status pass active 0`
   no stale; run the coverage-gap gate sim → green. Merge; push; REAL CI green. **No release**
   (gate-config + accept-ledger change, not shipped SKILL content). Runner pin N/A (repo-B is its own
   runner).
3. **repo-P** (`feat/phase3-c2`): re-pin `check.yml` clone `--branch v0.7.2 → v0.7.5` (keep runner
   pin `v0.8.1` — repo-B's runner is unchanged); **prune the 20 stale accepts** (W8201×8, W8202×7,
   W8205×5); reconverge (same wave sim with subprocess-capture coverage-gap); `ruff check` +
   `ruff format --check` locally; merge; push; REAL CI green. **No release.**

**Pin-safety check (binding):** before pushing each gate re-pin, diff the wave leaves between v0.7.2
and v0.7.5 (`git -C /tmp/leaves` clones) and confirm the **only** changed wave leaf is
`perf-smell-audit` (C1 changed only the non-wave `test-audit-pipeline`; B0 changed no leaf). The
coverage-gap-audit leaf (used by the separate coverage-gap gate) is unchanged v0.7.2→v0.7.5, so
bumping the shared clone tag is behavior-safe for it.

## Falsifiable DONE

- repo-A v0.7.5 shipped (narrowed leaf + honest SKILL.md), REAL CI green incl convergence-gate +
  coverage-gap gate.
- repo-B/repo-P gate pins bumped to v0.7.5; **49 stale perf-smell accepts pruned** (repo-B 29 / repo-P
  20); both reconverge (`check_wave_baseline` → `pass active 0`, no stale) in REAL CI; coverage-gap
  gate stays green.
- The accept-count reduction (77 → 28) recorded in `c2-evidence/`.

## Honest no-win exit (recorded, not taken)

If the narrowed leaf had lost true signal (a DROP code with a genuine fix) or failed to reduce
accepts, the change would NOT ship. The evidence (49 FP / 0 fixes for the DROP trio; genuine fixes
preserved in the KEEP set) is why it ships.

## Non-goals

- Not touching repo-A's *separate* self-audit perf-smell scope (the deferred 589-finding item in
  `SP15-CANDIDATES.md`) — that is a different engine boundary.
- No change to the wave runner, the coverage-gap gate logic, or any other leaf.
- No repo-B/repo-P version bump (their shipped SKILL content is unchanged).
