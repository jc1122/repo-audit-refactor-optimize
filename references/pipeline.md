# Pipeline

## Stage Order

Run the orchestrator in five stages:

1. Discovery
2. Diagnose
3. Synthesize
4. Execute
5. Verify

Do not skip the discovery stage. A bad repository profile causes wrong lane activation and wasted work.

## Discovery Artifacts

Capture at least:

- languages present
- build and test systems
- benchmark entrypoints
- likely generated or vendor directories
- deterministic or flaky verification surfaces
- likely hotspot directories or binaries

If the repository is mixed-language, note which language owns the dominant runtime path and which language owns the dominant verification surface. Those are often different.

## Diagnose Stage

Prefer three diagnosis lanes:

- test lane
- code health lane
- performance lane

Run independent lanes in parallel only after the repository profile is complete.

### Parallelism Rules

Allow parallel execution when:

- lanes read shared files but do not modify them
- benchmark collection does not interfere with test infrastructure
- subagents can stay in separate output directories

Keep sequential execution when:

- the same files will be rewritten
- baseline performance collection depends on a stable, already-fixed test loop
- the repo has a single fragile build system or shared mutable environment

## Recommended Artifact Layout

Write temporary outputs into one run-specific directory such as:

```text
/tmp/repo-audit-refactor-optimize/<repo-name>/<timestamp>/
```

Store:

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

## Completion Criteria

A run is complete only when:

- all executed batches have verification evidence
- unexecuted findings remain clearly labeled as recommendations
- the final summary distinguishes verified work from deferred work
