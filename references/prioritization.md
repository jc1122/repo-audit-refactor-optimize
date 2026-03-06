# Prioritization

## Goal

Turn raw findings into a backlog that is actionable, verifiable, and safe to execute incrementally.

## Ranking Dimensions

Score each finding on these dimensions:

- **Impact:** expected gain in correctness, maintainability, or performance
- **Confidence:** strength of evidence supporting the finding
- **Risk:** likelihood of regression or unintended behavior change
- **Effort:** implementation and verification cost

Prefer findings with:

- high impact
- high confidence
- low to moderate risk
- low to moderate effort

## Finding Types

### Safe Cleanup

Examples:

- dead code removal with clear reachability evidence
- naming cleanup
- local simplification
- obvious test fixture cleanup
- deterministic benchmark harness cleanup

Default policy: execute automatically if verification is straightforward.

### Structural Refactor

Examples:

- module splits
- API boundary cleanup
- ownership or data-flow restructuring
- removing anti-pattern-driven indirection

Default policy: batch carefully and verify after each step.

### Performance Optimization

Examples:

- algorithm changes
- allocation reduction
- cache-friendlier layout
- branch reduction
- low-level native or assembly adjustments

Default policy: require baseline evidence before the change and measured evidence after the change.

## Batch Construction Rules

Build batches that satisfy all of the following:

- one dominant intent per batch
- minimal overlap in edited files
- independent verification surface
- clear rollback boundary

Avoid:

- mixing stylistic cleanup with deep perf changes
- combining many weak findings into one broad rewrite
- hiding risky changes inside a cleanup batch

## Default Execution Order

Use this order unless evidence argues otherwise:

1. stabilize deterministic tests and benchmarks
2. apply safe cleanup
3. execute structural refactors
4. execute measured performance optimization
5. rerun broad verification and summarize remaining recommendations

## When to Defer

Defer a finding when:

- evidence is weak
- the verification loop is flaky
- the change crosses a public or externally consumed boundary
- the benchmark variance is too high to support the claim
- the best subskill support is missing for the target language
