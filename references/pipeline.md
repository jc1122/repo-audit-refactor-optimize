# Pipeline

## Stage Order

Run the orchestrator in six stages:

1. Bootstrap
2. Discovery
3. Diagnose
4. Synthesize
5. Execute
6. Verify

Do not skip Bootstrap or Discovery. A bad dependency profile or a bad repository profile causes wrong lane activation and wasted work.

## Bootstrap Stage

Run `scripts/check_skill_requirements.py` before any repository diagnosis. Read the bootstrap report first and decide whether the current session is:

- `full`
- `degraded`
- `manual`
- `blocked`

If the report says `stop_before_discovery`, stop. If the report says the required install would only be `available_next_run`, restart before continuing.

## Discovery Artifacts

Capture at least:

- languages present
- build and test systems
- benchmark entrypoints or benchmark gaps
- likely generated or vendor directories
- deterministic or flaky verification surfaces
- likely hotspot directories or binaries

If the repository is mixed-language, note which language owns the dominant runtime path and which language owns the dominant verification surface. Those are often different.

## Diagnose Stage

Prefer three diagnosis lanes:

- test lane
- code health lane
- performance lane

Run independent lanes in parallel only after Bootstrap and Discovery are complete.

Bootstrap and Discovery form a sequential barrier. All diagnosis lanes must wait for both artifacts. Once available, dispatch lanes concurrently — they read shared files but do not write.

### Parallelism Rules

Allow parallel execution when:

- lanes read shared files but do not modify them
- benchmark collection does not interfere with test infrastructure
- subagents can stay in separate output directories

Keep sequential execution when:

- the same files will be rewritten
- baseline performance collection depends on a stable, already-fixed test loop
- the repo has a single fragile build system or shared mutable environment

When dispatching to subagents, assign each lane a separate output subdirectory and limit the orchestrator's role to dispatching, collecting results, and synthesizing. This preserves the orchestrator's context window for high-level decisions.

## Recommended Artifact Layout

Write temporary outputs into one run-specific directory such as:

```text
/tmp/repo-audit-refactor-optimize/<repo-name>/<timestamp>/
```

Store:

- `bootstrap/`
- `repo_profile.json`
- `test/`
- `code_health/`
- `perf/`
- `backlog.json`
- `summary.md`
- `verification/`

Preserve raw outputs from subskills instead of overwriting them with summaries.

## Synthesis Stage

Convert all findings into normalized backlog items containing:

- title
- lane
- affected paths
- evidence
- impact
- confidence
- risk
- estimated effort
- proposed subskill for execution

Combine equivalent findings from multiple lanes into one backlog item with multiple evidence sources.

## Execution Batching

Use these batch types:

- `cleanup`
- `refactor`
- `performance`

Do not mix broad `refactor` and `performance` work in the same batch unless the benchmark evidence directly justifies the structural change.

Keep each batch independently verifiable. A batch should fail or pass on its own.

## Review and Escalation

Escalate before execution when:

- the change would alter public API shape
- the performance evidence is weak or noisy
- the benchmark is non-deterministic
- the test suite is too flaky to verify outcomes
- assembly changes are suggested without strong profiling evidence
- bootstrap has only a manual fallback for a lane that would otherwise change high-risk code

## Completion Criteria

A run is complete only when:

- bootstrap findings and lane states are preserved in the artifact set
- all executed batches have verification evidence
- unexecuted findings remain clearly labeled as recommendations
- the final summary distinguishes verified work from degraded-mode work and deferred work
