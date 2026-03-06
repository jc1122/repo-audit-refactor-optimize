# Activation Matrix

## Core Rule

Activated diagnosis lanes are independent read-only analyses and should be dispatched in parallel when bootstrap and discovery are complete.

Activate subskills based on repository shape, language, verification surface, and bootstrap availability. Do not treat the skill list as flat. Each lane must resolve to `full`, `degraded`, `manual`, or `blocked`.

## Test Lane

### Python + Pytest

- Preferred: `test-audit-pipeline`
- Fallback: `test-quality-assurance` + `test-redundancy-triage`
- Optional: `hypothesis-testing`
- Manual fallback: deterministic manual test audit
- Blocking: no

Interpretation:

- `full` when `test-audit-pipeline` is usable now
- `degraded` when the TQA + redundancy pair is usable now
- `manual` when no Python audit skills are usable now

### Non-Python Test Surfaces

- Preferred: none from the current Python-specific audit stack
- Manual fallback: deterministic manual test-loop review
- Blocking: no

Record the tooling gap instead of pretending that Python-specific audit results generalize automatically.

## Code Health Lanes

### Python-Heavy Repositories

- Preferred: `m15-anti-pattern`, `refactoring`, `python-code-quality`, `python-code-style`
- Optional: `dignified-code-simplifier`
- Manual fallback: manual Python code-health review
- Blocking: no

Interpretation:

- `full` when the preferred set is usable now
- `manual` otherwise

### C-Heavy Repositories

- Preferred: `m15-anti-pattern`, `refactoring`, `cpp-coding-standards`
- Manual fallback: manual C code-health review
- Blocking: no

### Rust-Heavy Repositories

- Preferred: `m15-anti-pattern`, `refactoring`, `rust-best-practices`
- Manual fallback: manual Rust code-health review
- Blocking: no

### Assembly-Heavy Repositories

- Preferred: `m15-anti-pattern` only for glue code and build integration
- Manual fallback: manual assembly-adjacent review
- Blocking: no

Notes:

- No dedicated assembly correctness or style skill is available in the current set.
- Treat assembly work as high-risk and performance-evidence driven.

## Performance Lane

### Local Algorithmic or Systems Performance

- Preferred: `perf-benchmark`
- Fallback companion: `m10-performance`
- Optional: `performance-testing` when service-level behavior matters
- Manual fallback: deterministic manual performance review
- Blocking: yes when no deterministic verification surface exists

Interpretation:

- `full` when `perf-benchmark` and `m10-performance` are usable now and a deterministic performance surface exists
- `degraded` when `perf-benchmark` is usable now but `m10-performance` is not
- `manual` when a deterministic test surface exists but no benchmark surface is available, or when the preferred benchmark skill is missing
- `blocked` when no deterministic test or benchmark surface exists at all

### Service or Throughput Performance

- Preferred: `perf-benchmark` + `m10-performance`
- Optional: `performance-testing`
- Manual fallback: manual service-level performance review with explicit tooling gap
- Blocking: yes when no deterministic verification surface exists

## Orchestration and Final Gate

### Bootstrap Helpers

- Preferred: `find-skills`, `skill-installer`
- Manual fallback: raw `npx skills find` and `npx skills add`
- Blocking: no

### Execution Helpers

- Preferred final gate: `verification-before-completion`
- Optional: `dispatching-parallel-agents`, `subagent-driven-development`
- Manual fallback: sequential execution plus explicit manual verification
- Blocking: no

## Mixed Repositories

For mixed Python/C or Python/Rust repositories:

- run the Python test audit lane if Python owns the main test harness
- run language-specific code-health lanes for each language with meaningful source ownership
- keep performance baselines aligned to the actual hot path, not merely the top-level language
- allow some lanes to be `full` while others remain `manual` or `blocked`
