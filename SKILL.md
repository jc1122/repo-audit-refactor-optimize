---
name: repo-audit-refactor-optimize
version: 0.4.3
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
- Performance lane: `perf-benchmark` then `perf-optimization`.

Use the deterministic diagnosis wave runner when installed leaves are available:

```bash
python3 scripts/run_diagnosis_wave.py \
  --repo <repo> --out-dir <diag-dir> --skills-root <skills-root> \
  --lanes code-health,security,hygiene,docs,dependency,hotspot
```

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
