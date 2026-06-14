---
name: repo-audit-refactor-optimize
version: 0.7.3
description: End-to-end repository diagnosis, remediation, and optimization orchestration built on the deterministic repo-audit-skills family. Use when the agent needs to audit a repository with deterministic code-health, coverage-gap, and test-audit lanes, synthesize a coverage-gated remediation backlog, execute safe refactor batches, benchmark and optimize performance, or run a full repo optimization pipeline from diagnosis through verified completion.
---

# Repo Audit Refactor Optimize

## Overview

Run a deterministic pipeline from bootstrap to verified completion. Start with capability discovery, then diagnosis, then execution, then verification.

Load the reference docs on demand:

- `references/bootstrap.md` - bootstrap policy, dependency state, overrides
- `references/pipeline.md` - stage order, artifacts, run report
- `references/activation-matrix.md` - preferred/fallback/manual/blocked behavior
- `references/prioritization.md` - backlog ranking and batching
- `references/verification.md` - evidence and rerun standards
- `references/remediation-playbook.md` - execution discipline

## Stage Order

0. Bootstrap. 1. Discovery. 2. Diagnosis. 3. Synthesis. 4. Execution. 5. Verification. 6. Run report write.

## Stage 0: Bootstrap

Run the checker first and only move forward on green or safe degraded mode:

```bash
python3 scripts/check_skill_requirements.py \
  --repo /path/to/target-repo \
  --out-dir /tmp/repo-audit-refactor-optimize/<repo-name>/<timestamp>
```

The checker is deterministic and non-mutating. It reads the manifest and writes `bootstrap/bootstrap_report.json`, `bootstrap/bootstrap_report.md`, and `bootstrap/install_plan.md`.

Rules:

- Continue when all blocking lanes are usable.
- Continue degraded when only non-blocking lanes are missing.
- Keep bootstrap installs explicit by user approval.
- Prefer `skill-installer` if available; otherwise use `npx skills add/find`.
- Never auto-install local/private skills.
- If new blocking skills are installed, restart the session before continuing.
- If optional skills are newly installed, continue in degraded mode and mark `available_next_run`.

## Stage 1: Discovery

Build repository profile: languages, build/test systems, generated/vendor boundaries, existing deterministic checks, and flaky loops.

## Stage 2: Diagnosis

Load `references/pipeline.md`, then run lanes relevant to repository profile and bootstrap result. Keep lanes read-only, run in parallel when independent, and merge outputs.

- Test lane: prefer `test-audit-pipeline` (coverage json), fallback `test-quality-assurance` and `test-redundancy-triage`.
- Code health lane: prefer `code-health-audit-pipeline`, fallback five leaf skills.
- Coverage lane: `coverage-gap-audit` from test coverage.
- Performance lane: `perf-benchmark` then `perf-optimization`. When no benchmark surface exists but a runnable Python surface does and `perf-benchmark` is usable, the lane is `synthesizable`: the agent runs `profile_discover.py`, picks a hotspot, authors `make_input(size)` via `synth_microbench.py`, measures with the `perf-benchmark` pipeline (callgrind tier preferred), gates with `synthesize_perf.py`, and may `graduate_benchmark.py` on demand. Synthesis is agent-triggered, never automatic.

Use the deterministic diagnosis wave runner when installed leaves are available:

```bash
python3 scripts/run_diagnosis_wave.py \
  --repo <repo> --out-dir <diag-dir> --skills-root <skills-root> \
  --lanes code-health,security,hygiene,docs,dependency,hotspot
```

By default (no `--source-prefix`) the wave excludes `tests/` and `**/fixtures/` so self-noise from test code does not crowd the backlog; pass `--source-prefix <dir>` to scope positively (which disables the default exclusion), `--exclude-prefix <dir>` to exclude additional trees, and `--baseline <accepted-residuals.json>` to suppress already-triaged findings (matched by the `{leaf,path,symbol,metric}` identity; suppressed/stale entries are written to `wave_findings.suppressed.json`). The orchestration lane resolves its process skills (`verification-before-completion`, `dispatching-parallel-agents`, `subagent-driven-development`) as always-available — they are harness-guaranteed, so the lane no longer degrades to `manual` when they are absent from a skills root.

Pass test coverage with `--coverage-json` where supported. Wave output includes `wave_findings.json`, `wave_summary.json`, and one lane directory per module.

## Stage 3: Synthesis

Merge findings into one backlog: deduplicate overlaps, separate cleanup/structural/performance work, rank by impact/confidence/effort/risk, and group executable batches.

## Stage 4: Execution

Use `references/remediation-playbook.md`. Execute verified batches: apply low-risk cleanup, pause on risky API or broad rewrites, isolate performance work unless evidence supports joint change, and rebaseline after meaningful batches.

Use `subagent-driven-development` for sequential multi-batch execution; use dispatch parallelism only for independent, non-overlapping subsystems.

## Stage 5: Verification

Load `references/verification.md`. Before completion, rerun smallest sufficient checks first, rerun the full relevant suite before closing batch, compare benchmark deltas with the same method, and separate verified from unverified claims.

Use `verification-before-completion` as final gate.

## Stage 6: Run Report

Write run report artifacts under `docs/audits/<run-id>/` (JSON and Markdown). Verification fails closed if `run_report.json` / `run_report.md` are missing or missing schema keys; do not claim completion without them.

## MPRR Remediation Track

The Massively-Parallel Redundancy Remediation (MPRR) engine runs unattended, gate-gated auto-remediation of redundancy findings in parallel. The engine lives in `scripts/mprr_run.py` (three subcommands, each answering `--help`). State is file-backed under a run directory; no state lives in chat.

### Subcommands

**plan** — emit file-disjoint remediation packets and persist run-state:

```
python scripts/mprr_run.py plan --run-dir DIR [--findings F.json] [--triage T.json] [--ceiling N] [--repo R]
```

Reads findings and triage inputs, selects the dispatchable batch (file-disjoint, up to `--ceiling`, default 8), emits the batch as a JSON array to stdout, and writes `mprr_state.json` + `mprr_events.jsonl` under `--run-dir`.

**integrate** — re-check scope and gate ladder, merge the conflict-free branch, release locks:

```
python scripts/mprr_run.py integrate --run-dir DIR --packet-id P --evidence E.json [--diff-files a.py,b.py] [--repo R] [--branch B] [--no-merge]
```

Verifies the worker only touched declared files (scope check) and that evidence satisfies the gate ladder for the finding's `remediation_class`. On pass, merges `--branch` into the current branch (unless `--no-merge`). Always releases the packet's file locks. Exit 0 on merged, 1 on discarded.

**reaudit** — check residual redundancy; exit code equals the count of remaining items (0 = converged):

```
python scripts/mprr_run.py reaudit [--findings F.json] [--triage T.json]
```

### File-level conflict rule

Two findings conflict iff they share at least one file. The scheduler only dispatches file-disjoint batches, so every merge is conflict-free by construction. A merge conflict reported at integration time is an `InvariantViolation` (hard stop — partitioner or worker bug), never a condition to resolve manually.

### Gate ladder

| `remediation_class` | Gates required for auto-merge |
|---|---|
| `mechanical` | tests green + lane re-audit resolves the finding |
| `refactor` | tests green + scoped mutation score ≥ 0.80 + duplication re-audit resolves the clone |
| `test_removal` | coverage parity + mutation parity + triage confidence == `"high"` only |

The orchestrator re-derives all gate evidence from artifacts; it never trusts a worker's self-reported "green".

### R2 admission

Signal MPRR makes visible: which redundancy findings are safely auto-remediable in parallel. No existing component hosts it: the wave runner and synthesis layer are advisory-only and do not manage locks, branch merges, or gate enforcement. Sunset plan: fold non-redundancy lanes into this engine in SP15.
