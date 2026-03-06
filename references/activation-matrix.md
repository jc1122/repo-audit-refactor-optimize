# Activation Matrix

## Core Rule

Activate subskills based on repository shape, language, and verification surface. Do not activate every subskill by default.

## Repository Shape

### Python-Heavy Repositories

Primary subskills:

- `test-audit-pipeline`
- `hypothesis-testing`
- `m15-anti-pattern`
- `refactoring`
- `python-code-quality`
- `python-code-style`
- `dignified-code-simplifier`
- `perf-benchmark`
- `m10-performance`

Strongest fit when the repo uses `pytest`, Python benchmarks, or Python-driven orchestration around native extensions.

### C-Heavy Repositories

Primary subskills:

- `m15-anti-pattern`
- `refactoring`
- `cpp-coding-standards`
- `perf-benchmark`
- `m10-performance`

Notes:

- No dedicated C test-quality or redundancy skill is available in the current set.
- Audit deterministic test execution manually when the suite is not Python-based.

### Rust-Heavy Repositories

Primary subskills:

- `m15-anti-pattern`
- `refactoring`
- `rust-best-practices`
- `perf-benchmark`
- `m10-performance`

Notes:

- No dedicated Rust test-redundancy skill is available in the current set.
- Use `cargo test` and benchmark baselines as verification inputs, but keep the limitation explicit.

### Assembly-Heavy Repositories

Primary subskills:

- `perf-benchmark`
- `m10-performance`
- `m15-anti-pattern` only for surrounding glue code and build integration

Notes:

- No dedicated assembly correctness or style skill is available in the current set.
- Treat assembly work as high-risk and performance-evidence driven.
- Avoid broad rewrites without profile data and deterministic verification.

## Test Surface Detection

### Python + Pytest

Activate:

- `test-audit-pipeline`
- `hypothesis-testing` when invariants exist
- `verification-before-completion` at the end

### Non-Python Tests

Activate:

- language-specific code health skills
- `perf-benchmark` if benchmark discipline matters
- manual deterministic test-loop review

Record the tooling gap instead of pretending that Python-specific audit results generalize automatically.

## Performance Surface Detection

### Local Algorithmic or Systems Performance

Activate:

- `perf-benchmark`
- `m10-performance`

### Service or Throughput Performance

Activate:

- `perf-benchmark`
- `m10-performance`
- `performance-testing` when the question depends on load, concurrency, or latency distributions

## Mixed Repositories

For mixed Python/C or Python/Rust repositories:

- run the Python test audit lane if Python owns the main test harness
- run language-specific code health lanes for each language with meaningful source ownership
- keep performance baselines aligned to the actual hot path, not merely the top-level language

## Orchestration Helpers

Activate:

- `dispatching-parallel-agents` when diagnosis lanes are independent
- `subagent-driven-development` when execution requires multiple reviewable batches
- `verification-before-completion` as the final gate for all repository shapes
