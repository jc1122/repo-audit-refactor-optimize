---
name: repo-audit-refactor-optimize
description: Structured repository audit with optional authorized fixes. Runs detection through the repo-audit CLI, ranks findings into a coverage-gated backlog, applies small verified batches only when fixes are requested, and reports evidence with remaining limits. Use when asked to audit a repo, review code health, or carry out an explicitly authorized cleanup.
metadata:
  version: 1.0.0
  requires: "repo-audit-checks >= 1.0.0"
---

# Repo Audit Refactor Optimize

## Scope rule

An audit never authorizes edits. Read-only analysis runs first and always.
Only make changes when the user explicitly asked for fixes, and only inside
the scope they granted. Say which mode you are in before you start.

Static checks must not import or execute target code. Checks that run tests,
profilers, or anything that executes the target need a trusted project context
and an isolated working area. Never silently import code during a static-only
audit.

## Prerequisites

Detection lives in the `repo-audit` command (package `repo-audit-checks`
v1.0.0+, owned by the repo-audit-skills repository). This skill ships a
launcher at `scripts/repo-audit` next to this file; it runs the isolated
environment created at install time, so no venv activation or global install
is needed. Let `SKILL_DIR` be the directory containing this SKILL.md:

```bash
"$SKILL_DIR/scripts/repo-audit" doctor
```

If the launcher reports no CLI, install it per `bootstrap/install.sh --help`
and stop if installation is not possible. A missing required check makes the
result incomplete; skipped checks never count as clean coverage.

## Workflow

1. Scope. Identify the repository, languages, build and test commands, and
   generated or vendored boundaries. Record what you will and will not touch.
2. Diagnose. Run the packaged CLI, selecting checks for the target:
   ```bash
   "$SKILL_DIR/scripts/repo-audit" scan --root <repo> --out-dir <run-dir> --checks <a,b>
   "$SKILL_DIR/scripts/repo-audit" scan --root <repo> --out-dir <run-dir> --preset code-health
   "$SKILL_DIR/scripts/repo-audit" scan --list-checks
   ```
   Every check stays individually selectable. Expensive checks that execute
   code are opt-in, never default. Keep the explicit output directory; never
   require report files inside the target repository.
3. Review. Read `run.json`, `findings.json`, and `report.md` from the run
   directory. Exit 0 means complete and clean, 1 means complete with findings,
   2 means incomplete or error. Failed requested checks make the result
   incomplete. Skipped, unsupported, and error states are reported as-is.
4. Prioritize. Rank by impact, confidence, risk, and effort (see
   `references/prioritization.md`). Files without covering tests are
   characterize-first: add behavior tests before remediating.
5. Fix only if authorized. Work in small coherent batches with one intent per
   batch, inspect the actual diff, and rerun the relevant checks and tests
   (see `references/remediation-playbook.md`). Test removal needs evidence of
   preserved behavior; no universal score threshold proves equivalence.
6. Compare on real measurements: same workload, same inputs, same method,
   matched environment — including stored audit runs:
   ```bash
   "$SKILL_DIR/scripts/repo-audit" compare --baseline <run-a> --current <run-b>
   ```
   A comparison is advisory evidence, never authorization to merge.
7. Report. Findings, changes with verification output, and remaining limits.
   Label each claim `verified improvement`, `verified neutral cleanup`,
   `verified regression`, `unverified hypothesis`, or `deferred recommendation`.

## Acceptance

A target may carry `.repo-audit/accept.json` with accepted residuals (reason,
expiry, ceilings). Accepted findings stay visible with their reason; stale
entries are reported. Malformed policy is a hard error, never silent. Details
in `references/acceptance.md`.

## Delegation

The host owns planning, edits, and Git. Use host-native delegation only when
available and useful; sequential execution in one agent is fully supported.
Pass each worker its scope, constraints, artifact locations, and expected
evidence, then review the combined result yourself. File-disjoint work does
not imply conflict-free behavior: shared interfaces and cross-file effects
still need combined-state validation.

## What this skill does not do

No automatic merging, no scheduler, no mandatory commits or checked-in report
files, no required full-suite tooling before starting. There is deliberately
no `fix`, `spawn`, `schedule`, or `merge` command: the host edits, the CLI
detects, and this skill holds the two apart. Removed v0.x machinery is mapped
in `references/MIGRATION.md`.
