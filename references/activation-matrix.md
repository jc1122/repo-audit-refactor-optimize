# Activation Matrix

## Core Rule

Activated diagnosis lanes are independent read-only analyses and should be dispatched in parallel when bootstrap and discovery are complete. All diagnosis lanes run first-party deterministic skills from the repo-audit-skills family; every lane resolves to `full`, `degraded`, `manual`, or `blocked`.

## Test Lane (`test-python`)

- Preferred: `test-audit-pipeline`
- Fallback: `test-quality-assurance` + `test-redundancy-triage`
- Manual fallback: deterministic manual test audit
- Blocking: no

`full` when `test-audit-pipeline` is usable now; `degraded` on the TQA + redundancy pair; `manual` otherwise. The test lane also produces the `coverage.json` artifact consumed by the coverage and code-health lanes (see pipeline.md).

### Non-Python Test Surfaces

No first-party audit stack exists. Perform a deterministic manual test-loop review and record the tooling gap explicitly. Never present Python-lane results as covering non-Python code.

## Code Health Lane (`code-health-python`)

- Preferred: `code-health-audit-pipeline` (runs complexity, duplication, dead-code, structure, and quality leaves, merges and ranks findings, exit 0/1/2)
- Fallback: the five leaf skills invoked directly (`complexity-audit`, `duplication-audit`, `dead-code-audit`, `structure-audit`, `quality-audit`)
- Manual fallback: manual review with the tooling gap recorded
- Blocking: no

`full` when the umbrella is usable; `degraded` when only the leaves are usable (run all five, merge by the shared finding schema); `manual` otherwise. When a `coverage.json` artifact exists, pass it through (`--coverage-json`) so the umbrella's artifact-gated coverage leaf runs too.

### Non-Python Code Health

There is no first-party C, Rust, or assembly code-health lane. This is a recorded tooling gap: review manually, keep changes perf-first and evidence-driven, and say so in the report. Do not substitute generic advice for deterministic findings.

## Coverage Lane (`coverage-python`)

- Preferred: `coverage-gap-audit` (consumes coverage.py JSON, emits TEST findings: untested / under-tested production files)
- Manual fallback: read the coverage report manually
- Blocking: no

This lane is the refactor-safety signal: its TEST findings gate remediation (see prioritization.md). It never runs tests itself; it consumes the test lane's coverage artifact.

## Performance Lane (`performance`)

- Preferred: `perf-benchmark`
- Manual fallback: manual performance reasoning over stable verification
- Blocking: yes (blocked only when the repo has neither a benchmark nor a deterministic test surface)

`full` when `perf-benchmark` is usable and a deterministic benchmark surface exists; `synthesizable` when there is no benchmark surface but a runnable test surface exists and `perf-benchmark` is usable (the agent may synthesize a focused microbenchmark — see pipeline.md); `manual` with a warning when only a test surface exists and `perf-benchmark` is not usable; `blocked` when neither a benchmark nor a deterministic test surface exists.

## Orchestration Lane (`orchestration`)

- Preferred: `verification-before-completion`
- Optional: `dispatching-parallel-agents`, `subagent-driven-development`
- Manual fallback: sequential batches with manual verification
- Blocking: no

These are process scaffolding, not diagnosis content; their absence degrades convenience, not evidence quality.
