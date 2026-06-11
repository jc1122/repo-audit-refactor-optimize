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

## Coverage-Gated Actionability

Cross-join every finding with the coverage lane's TEST findings before ranking:

- A finding in a file **with** a TEST finding (untested / under-tested) is **not auto-executable**. Demote it to characterize-first: write behavior/golden tests for the file's current contract, then remediate under that protection. This rule has priority over impact scores.
- A finding in a covered file keeps its computed rank.
- TEST findings themselves rank as test-debt work items (add tests), never as refactor licenses.

This generalizes the Actionability Rule proven in the repo-audit-skills dogfooding runs: advisory findings in untested code are frozen until tests exist.

PERF findings rank by dimension priority (algorithmic scaling above all hardware dimensions) and are coverage-gated like all others: an uncovered hot file is characterize-first.

## T4 Taxonomy v2

Every finding is assigned exactly one class below before scheduling:

| Class | Meaning | Primary action | Justification rule |
|---|---|---|---|
| `accepted-mechanical` | High-confidence, low-risk, local mechanical signal | Execute when coverage rules pass | Required: one sentence naming why the work is safe and the expected gain |
| `deferred-structural` | Architectural, API-boundary, or broad refactor risk | Defer to a structural batch with explicit architecture owners | Required: one sentence naming boundary risk and owning team/piece |
| `coverage-gated` | Any file in scope with a `TEST` finding or weak behavioral lock | Characterize-first then remediate | Required: one sentence naming the missing/insufficient coverage gap |
| `won't-fix-FP` | Confirmed false positive, environment mismatch, or unverifiable legacy intent | Keep as non-actionable debt and explain in backlog notes | Required: one sentence naming why it is not actionable now |

Apply these classes to the same findings backlog that is already maintained for execution.

Notes:

- A `won't-fix-FP` row is never silently dropped.
- It must remain present in run reports and in baseline/frozen logs when present in that source so trend analysis stays complete.
- A justification entry is mandatory for every finding row, even when the row is not planned for execution.

## Finding Types

### Safe Cleanup

Signal: `LINT`, `FORMAT`, `DELETE` (high-confidence), same-file `MERGE`. See `references/remediation-playbook.md` for per-signal procedure.

Examples:

- dead code removal with clear reachability evidence
- naming cleanup
- local simplification
- obvious test fixture cleanup
- deterministic benchmark harness cleanup

Default policy: execute automatically if verification is straightforward.

### Structural Refactor

Signal: `EXTRACT`, `DECOMPOSE`, `RESTRUCTURE`, `SIMPLIFY`, cross-file `MERGE`. See `references/remediation-playbook.md` for per-signal procedure.

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
