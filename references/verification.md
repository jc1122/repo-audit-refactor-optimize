# Verification

## Verification Principle

Do not claim improvement without evidence. Separate implemented-and-verified work from recommendations and hypotheses.

## Baseline Rules

Before modifying code:

- capture the current test result for the affected surface
- capture the current benchmark result for the affected hot path
- record environment details that matter for reproducibility

For performance claims, use the same:

- machine class
- compiler or interpreter settings
- environment variables
- dataset or fixture size
- benchmark command

## Verification Sequence

Run verification in this order:

1. smallest affected test or benchmark surface
2. broader subsystem surface
3. full relevant suite

If the smallest affected surface fails, stop and fix the regression before running broader verification.

When multiple lanes complete in parallel, run lane-specific verification concurrently. Only the final cross-lane verification step needs sequential execution.

## Test Verification

Prefer deterministic commands and stable fixtures.

Record:

- command run
- pass or fail status
- any important warnings
- whether the result reflects a stable or flaky loop

If the suite is flaky:

- state that clearly
- avoid making strong success claims
- prioritize stabilization work before broader optimization

## Benchmark Verification

For benchmark comparisons:

- keep the command identical between baseline and follow-up
- keep the data and input size identical
- avoid comparing cold and warm runs without noting the difference
- compare variance, not just a single best number, when the harness supports it

Use `perf-benchmark` outputs as the authoritative source when available.

## Final Claim Categories

Use one of these labels in final reporting:

- `verified improvement`
- `verified neutral cleanup`
- `verified regression`
- `unverified hypothesis`
- `deferred recommendation`

## Final Gate

Before completion:

- apply `verification-before-completion`
- ensure every executed batch has verification evidence
- ensure every unexecuted item is labeled as deferred or unverified
- avoid summary language that implies proof where only intuition exists
