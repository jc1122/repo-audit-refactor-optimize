---
name: repo-audit-refactor-optimize
description: End-to-end repository diagnosis, remediation, and optimization orchestration for Python, C, Rust, and assembly codebases. Use when the agent needs to audit a repository, assess test quality and redundancy, bootstrap the relevant subskills, stabilize deterministic tests and benchmarks, propose or execute refactors and cleanups, benchmark and optimize performance, or run a full repo optimization pipeline from diagnosis through verified completion.
---

# Repo Audit Refactor Optimize

## Overview

Run an end-to-end repository optimization program. Start with a bootstrap pass that checks which subskills are relevant and usable in the current agent session. Only after bootstrap succeeds or degrades safely should the workflow continue into repository discovery, diagnosis, execution, and verification.

Keep the top-level flow here and load the reference files only when needed:

- `references/bootstrap.md` for root search order, dependency states, override files, and install policy
- `references/pipeline.md` for stage order, concurrency rules, artifact layout, and batch structure
- `references/activation-matrix.md` for lane-specific preferred, fallback, manual, and blocked behavior
- `references/prioritization.md` for ranking findings and defining execution batches
- `references/verification.md` for baseline, rerun, and claim-evidence standards

## Operating Model

Follow this sequence:

0. Bootstrap subskills and current-session capabilities.
1. Discover repository shape and verification surfaces.
2. Diagnose tests, code health, and performance.
3. Synthesize a ranked remediation backlog.
4. Execute safe cleanup, refactor, and optimization batches.
5. Verify the resulting claims before completion.

Treat this skill as an orchestrator. Reuse specialized subskills instead of re-implementing their internals. Keep raw outputs from each lane, then merge them into a single backlog and verification summary.

## Stage 0: Bootstrap

Run the checker before Discovery:

```bash
python3 scripts/check_skill_requirements.py \
  --repo /path/to/target-repo \
  --out-dir /tmp/repo-audit-refactor-optimize/<repo-name>/<timestamp>
```

Run `python3 scripts/check_skill_requirements.py --help` for override and extra-root flags.

The checker is deterministic and non-mutating. It reads `scripts/skill_bootstrap_manifest.json`, pre-scans the target repository, resolves the relevant lanes, checks usable skill roots, and writes:

- `bootstrap/bootstrap_report.json`
- `bootstrap/bootstrap_report.md`
- `bootstrap/install_plan.md`

Then read the report and apply these rules:

- Continue immediately when all blocking lanes are usable.
- Continue in degraded mode when only non-blocking skills are missing and the report provides a safe manual fallback.
- Install public skills only after explicit user approval.
- Prefer `skill-installer` when it is already available; otherwise fall back to raw `npx skills add` or `npx skills find`.
- Never auto-install local or private skills. Without a configured source mapping they remain `manual_only`.
- If a blocking skill is installed during bootstrap, stop and restart the agent session before continuing.
- If only optional skills were installed, continue the current run in degraded mode and mark them as `available_next_run`.

Load `references/bootstrap.md` before interpreting the report.

## Stage 1: Discovery

Begin by building a repository profile.

- Identify primary languages and major directories.
- Detect build and test systems such as `pytest`, `cargo`, `cmake`, `meson`, `make`, and benchmark runners.
- Separate product code from generated code, vendor code, fixtures, snapshots, and benchmark artifacts.
- Detect whether deterministic verification is already available.
- If tests or benchmarks are flaky, stabilize the verification loop before broad optimization work.

Load `references/activation-matrix.md` once the repo profile is clear.

## Diagnosis Lanes

Load `references/pipeline.md` before dispatching diagnosis lanes.

Once bootstrap and discovery artifacts are available, dispatch independent diagnosis lanes in parallel. Each lane reads shared files but does not modify them. Use `dispatching-parallel-agents` when available, or instruct subagents with non-overlapping output directories.

Activate only the lanes that match the repository profile and the bootstrap result.

### Test Lane

Use:

- `test-audit-pipeline` as the preferred Python audit lane
- `test-quality-assurance` plus `test-redundancy-triage` as the degraded fallback
- `hypothesis-testing` when invariants, parsers, graph logic, numeric code, or serialization surfaces are present
- `verification-before-completion` only as the final gate, not as a replacement for diagnosis

For non-Python test ecosystems, perform deterministic test-loop assessment and structural review, and keep the tooling gap explicit.

### Code Health Lane

Use:

- `m15-anti-pattern` to diagnose code smells, anti-patterns, and risky structure
- `refactoring` to execute structural changes once the findings are concrete
- `python-code-quality`, `python-code-style`, and `dignified-code-simplifier` for Python
- `cpp-coding-standards` for C-heavy repositories
- `rust-best-practices` for Rust-heavy repositories

Do not start with refactoring. Start with evidence, then restructure.

### Performance Lane

Use:

- `perf-benchmark` to establish baselines, hotspot rankings, and benchmark discipline
- `m10-performance` only after a bottleneck is proven
- `performance-testing` only when the repository is throughput or latency oriented and the question is service-level performance rather than local code-path performance

Treat assembly as a perf-first, evidence-driven lane. No dedicated assembly audit subskill is currently available, so prefer profiling evidence and conservative change control over broad structural edits.

## Synthesis

Merge the lane outputs into a single remediation backlog.

- Deduplicate overlapping findings.
- Separate safe cleanup from structural refactors and performance-sensitive work.
- Rank by impact, confidence, implementation cost, and regression risk.
- Prefer small, verified batches over sweeping rewrites.

Load `references/prioritization.md` to score and group findings.

## Execution

Execute changes in batches.

- Apply safe cleanup automatically when behavior is preserved and the blast radius is low.
- Pause before risky API changes, speculative optimizations, or broad architectural rewrites.
- Keep performance changes separate from broad refactors unless the same evidence supports both.
- Rebaseline after each meaningful batch.

For diagnosis parallelism (read-only lanes), prefer concurrent dispatch as the default.

For execution parallelism (write lanes), keep sequential execution as the default:

- Use `subagent-driven-development` for sequential multi-batch execution with review loops.
- Use `dispatching-parallel-agents` only for clearly independent subsystems with no shared-state or overlapping-file risk.

## Verification

Load `references/verification.md` before claiming progress or completion.

Apply these rules:

- Re-run the smallest sufficient verification surface first.
- Re-run the full relevant suite before closing the batch.
- Compare benchmark results using the same environment, inputs, and methodology as the baseline.
- Distinguish verified improvements from verified-neutral cleanup and from unverified hypotheses.
- Use `verification-before-completion` as the final evidence gate.

Never claim that the repository is improved merely because the code looks cleaner. Claims require test or benchmark evidence.

## Required References

Consult these files during execution:

- `references/bootstrap.md`
- `references/pipeline.md`
- `references/activation-matrix.md`
- `references/prioritization.md`
- `references/verification.md`
