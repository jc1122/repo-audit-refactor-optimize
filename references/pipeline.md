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

Prefer five diagnosis lanes:

- test-python lane
- code-health-python lane
- coverage-python lane
- performance lane
- orchestration lane

Run independent lanes in parallel only after Bootstrap and Discovery are complete.

Bootstrap and Discovery form a sequential barrier. All diagnosis lanes must wait for both artifacts. Once available, dispatch lanes concurrently — they read shared files but do not write.

### Diagnosis Wave Runner

When installed leaves are available, prefer running one deterministic wave:

```bash
python3 scripts/run_diagnosis_wave.py --repo <repo> --out-dir <diagnose-dir> --skills-root <skills-root> --lanes code-health,security,hygiene,docs,dependency,hotspot
```

The wave emits:

- `wave_findings.json` (merged findings for all requested lanes)
- `wave_summary.json` (lane completion states)
- per-lane output folders: `code-health/`, `security/`, `hygiene/`, `docs/`, `dependency/`, `hotspot/`

Use `--coverage-json` when present in the test artifact so code-health can run artifact-gated checks.

**Scoping and suppression.** With no `--source-prefix`, the wave excludes `tests` and `fixtures` by default so the orchestrator's own test code does not generate self-noise; an explicit `--source-prefix <dir>` scopes positively and disables the default exclusion, and `--exclude-prefix <dir>` adds further exclusions (honored by the code-health/security/dependency lanes that support it). Pass `--baseline <accepted-residuals.json>` — a JSON array of accepted residuals keyed by the `{leaf, path, symbol, metric}` identity — to suppress already-triaged findings; suppressed findings and stale baseline entries (baseline identities that matched nothing) are written to `wave_findings.suppressed.json`. This same identity drives `.repo-audit/accept.json` auto-discovery (below). The convergence gate `check_wave_baseline.py` no longer reads a separate `wave_baseline.json`; instead it trusts the wave's report/accept partition (Option A): it passes only when the active set (`wave_findings.json`) is empty **and** the accept sidecar's `stale` list is empty, so suppression and the ratchet can never disagree.

**Acceptance policy (auto-discovery).** Place `.repo-audit/accept.json` in the audited
repo to mark findings acceptable without changing audit leaves. The wave auto-discovers it
at the `report` stage; the MPRR engine honors it at the `remediation` stage. Three match
kinds are supported: `finding` (exact `{leaf,path,symbol,metric}` identity), `path` (repo-
relative `fnmatch` glob against a finding's `path` or `files`), and `rule` (`leaf`/`metric`
subset, AND). Every accepted finding is recorded with its reason in a sidecar:

- `wave_findings.accepted.json` — findings accepted at the reporting stage (the old
  `wave_findings.suppressed.json` is still written for back-compat).
- `mprr_excluded.json` — findings excluded from remediation by the MPRR engine.

The policy is **fail-closed**: a malformed or invalid `accept.json` is a hard error —
the wave and engine exit non-zero rather than silently ignoring the file or accepting
everything. Validate with `python3 scripts/validate_accept.py --file <repo>/.repo-audit/accept.json`.
Pass `--accept <file>` to the wave runner to merge an additional policy file; legacy
`--baseline` rows are automatically adapted as report-stage `finding` entries. The old
`scripts/remediation_excludes.json` (dead-code section `exclude_paths` globs) is honored
as a back-compat remediation fallback. See `references/acceptance.md` for the full
authoring guide.

**MPRR self-engine merge guard.** When the merge-parallel-review-runner integrates a packet, `mprr_integrate.self_guard` refuses to auto-merge edits to the engine's own `scripts/*.py` when the target repo resolves to the engine's own repository (or the target is unresolvable — it fails closed). This is defense-in-depth for the in-place/self-modification topology; such edits require human review rather than automatic merge.

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
- `coverage/`
- `perf/`
- `orchestration/`
- `backlog.json`
- `summary.md`
- `verification/`

Preserve raw outputs from subskills instead of overwriting them with summaries.

## Run Report (required artifact)

Every orchestration run MUST end by writing a run report into the AUDITED repository at:

    docs/audits/<YYYYMMDDTHHMMSSZ>/run_report.json
    docs/audits/<YYYYMMDDTHHMMSSZ>/run_report.md

(timestamp = run start, UTC, compact ISO). `run_report.json` minimal schema (all keys required):

- `schema_version`: 2
- `repo_root`: absolute path audited
- `started_utc`, `finished_utc`: ISO timestamps
- `orchestrator_skill_version`: this SKILL.md frontmatter version
- `lanes`: {lane_name: state} from the bootstrap report
- `findings_totals`: {signal: count} across all diagnosis lanes
- `backlog`: {"accepted": N, "deferred": N, "coverage_gated": N, "wont_fix": N}
- `batches`: [{"id", "signal", "files", "result": "accepted"|"discarded", "evidence"}]
- `verification`: [{"command", "exit_code"}]
- `warnings`: [str]

`run_report.md` is the human rendering of the same content. A run that did not write both
files is NOT complete: the Verification stage fails closed on their absence.

Validation is required:

- run `scripts/validate_run_report.py --run-dir <run-dir>`
- `--schema 1` is accepted only for historical reports

## Coverage Artifact Handoff

The test lane produces a single `coverage.json` (coverage.py JSON format) under its artifact directory. Two consumers depend on it:

1. `coverage-gap-audit --coverage-json <path> --root <repo>` — the coverage lane's TEST findings.
2. `code-health-audit-pipeline ... --coverage-json <path>` — enables the umbrella's artifact-gated coverage leaf (repo-audit-skills v0.3.0+).

Sequencing rule: the coverage and code-health lanes may start before the test lane completes, but their coverage-dependent outputs must be produced (or re-produced) after `coverage.json` exists. If no coverage artifact can be produced, run the code-health lane without `--coverage-json` and mark the coverage lane `manual` in the run summary — never fabricate testedness.

## Benchmark Synthesis (`synthesizable` performance lane)

When the performance lane resolves to `synthesizable` (no benchmark surface, but a runnable
Python surface exists and `perf-benchmark` is usable), the agent may synthesize a focused
microbenchmark instead of leaving performance work manual. The flow is agent-triggered, never
automatic: `profile_discover.py` (or the pipeline's own `perf` hotspots) **+** `perf-smell-audit`
PERF findings → pick a hotspot → `synth_microbench.generate` → author `make_input(size)` →
`perf-benchmark` pipeline (callgrind tier preferred) → `synthesize_perf.py` gate → on pass,
`select_candidate` + apply one change + re-measure + `verify_win` → optional `graduate_benchmark.py`.

All synthesis work writes into the run's `perf/` directory: the harness (`bench_<name>.py`,
`make_input.py`, `synth_spec.json`), the pipeline's `benchmark_summary.json`, and the gate's
`gate.json` + `synthesis_report.md`. Only `graduate_benchmark.py` writes into the audited repo
(copying the proven harness into `benchmarks/<name>/`); the perf trend ledger stays owned by
`perf-benchmark --baseline-ledger`.

Honest-refusal contract — `synthesize_perf.decide_gate` returns one of three verdicts and never
fabricates a win: **pass** (gate-quality: deterministic instruction count, or wall-time CV within
bound, on non-degenerate work — may back a win-claim), **refuse** (measured but not gate-quality:
degenerate O(1) work, or wall-time noise with no deterministic tier — advisory only, lane stays
`manual`), and **error** (no usable scaling evidence — fix the harness/sizes, not a verdict on the
code). After optimization, `verify_and_decide` consumes `verify_win`'s `accept`/`reject` verdict
and emits an explicit revert directive on anything other than `accept`. See
`docs/superpowers/specs/2026-06-13-synthesized-perf-benchmark-design.md`.

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
