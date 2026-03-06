---
name: repo-audit-refactor-optimize
description: End-to-end repository diagnosis, remediation, and optimization orchestration for Python, C, Rust, and assembly codebases. Use when Codex needs to audit a repository, assess test quality and redundancy, stabilize deterministic tests and benchmarks, propose or execute refactors and cleanups, benchmark and optimize performance, or run a full repo optimization pipeline from diagnosis through verified completion.
---

# Repo Audit Refactor Optimize

## Overview

Run an end-to-end repository optimization program. Start by profiling repository shape and verification surfaces. Diagnose tests, code health, and performance in parallel where safe. Merge the findings into ranked work batches, execute low-risk changes first, and verify every claimed improvement before completion.

Keep the top-level flow here and load the reference files only when needed:

- `references/pipeline.md` for stage order, concurrency rules, and batch structure
- `references/activation-matrix.md` for language and repo-shape based subskill selection
- `references/prioritization.md` for ranking findings and defining execution batches
- `references/verification.md` for baseline, rerun, and claim-evidence standards

## Operating Model

Follow this sequence:

1. Discover repository shape and available verification surfaces.
2. Diagnose tests, code health, and performance.
3. Synthesize a ranked remediation backlog.
4. Execute safe cleanup, refactor, and optimization batches.
5. Verify the resulting claims before completion.

Treat this skill as an orchestrator. Reuse specialized subskills instead of re-implementing their internals. Keep raw outputs from each lane, then merge them into a single backlog and verification summary.

## Discovery

Begin by building a repository profile.

- Identify primary languages and major directories.
- Detect build and test systems such as `pytest`, `cargo`, `cmake`, `meson`, `make`, and custom benchmark runners.
- Separate product code from generated code, vendor code, fixtures, snapshots, and benchmark artifacts.
- Detect whether deterministic verification is already available.
- If tests or benchmarks are flaky, stabilize the verification loop before broad optimization work.

Load `references/activation-matrix.md` once the repo profile is clear.

## Diagnosis Lanes

Activate only the lanes that match the repository profile.

### Test Lane

Use:

- `test-audit-pipeline` for Python/pytest-heavy repositories that can produce meaningful coverage and redundancy data
- `hypothesis-testing` when invariants, parsers, graph logic, numeric code, or serialization surfaces are present
- `verification-before-completion` only as the final gate, not as a replacement for diagnosis

For non-Python test ecosystems, perform deterministic test-loop assessment and structural review, but acknowledge the current tooling gap explicitly.

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

Load `references/pipeline.md` before dispatching multiple lanes or batching work.

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

For implementation orchestration:

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

- `references/pipeline.md`
- `references/activation-matrix.md`
- `references/prioritization.md`
- `references/verification.md`
