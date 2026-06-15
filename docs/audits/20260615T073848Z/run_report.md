# Dogfood Run — Skillset on Skillset

- **Run ID:** 20260615T073848Z
- **Window (UTC):** 2026-06-15T07:38:48Z → 2026-06-15T08:27:16Z
- **Orchestrator:** repo-audit-refactor-optimize @ v0.8.1-52-ga54239c
- **Scope:** every audit skill run on the whole skillset across all three family repos
  (repo-A `repo-audit-skills`, repo-B `repo-audit-refactor-optimize`, repo-P `perf-benchmark-skill`).
- **Result:** converged — 1 genuine defect found and fixed (+ regression test), 2 consequent
  accept-ledger prunes, **0 unaccepted findings remaining**, all CI gates green on all 3 repos.

## Genuine defect found (and fixed)

**`run_diagnosis_wave.py` dropped `--source-prefix` for the `perf-smell` lane.**
`_append_scope_args` only forwarded source scoping to `code-health`, `security`, and
`dependency`. `perf-smell` fell through, so `perf_smell_audit` ran `root.rglob("*.py")` over the
entire tree — including an untracked local `.venv/` — and the wave hung scanning thousands of
`site-packages` files via perflint. Every other rglob-based leaf shares the footgun, but only
perf-smell was both (a) unscoped by the orchestrator and (b) slow enough to hang visibly.

- **Fix:** add `"perf-smell"` to the source-scoping lane set (one line).
- **Regression test:** `test_perf_smell_lane_receives_source_prefix` (TDD red → green).
- **Verification:** 34/34 wave tests; 318/318 repo-B suite.

### Consequent remediation (coordinated prune)

The convergence gates (Option A) run the wave with `--source-prefix`. Pre-fix, perf-smell ignored
it and emitted findings from `tests/` (and `benchmarks/`), which had been accepted in
`.repo-audit/accept.json`. Post-fix those findings correctly disappear, so their accepts went
stale and the gate failed on `stale_acceptances`. Pruned:

- **repo-B:** 10 stale `perf-smell` accepts under `tests/` (accept entries 36 → 26).
- **repo-P:** 3 stale `perf-smell` accepts under `tests/` + `benchmarks/` (40 → 37).

## Verification (final sweep, all green)

| Repo | Gates |
|------|-------|
| repo-A `repo-audit-skills` | `run_checks` 10/10 cheap + 1/1 heavy (coverage), 0 failed; self-audit ratchet 40/40 |
| repo-B `repo-audit-refactor-optimize` | pytest 318 · release pass · convergence (26 accepted / 0 active) · coverage-gap pass |
| repo-P `perf-benchmark-skill` | ruff check + format · pytest 124 · convergence (45 accepted / 0 active) · coverage-gap pass |

## Environment notes (local fidelity to CI)

- Installed the repos' own CI-pinned tools that were missing locally: `bandit==1.9.4`,
  `pylint==3.3.9`, `perflint==0.8.1`, `mutmut==3.6.0` into repo-A's `.venv`; `hypothesis==6.155.2`
  and `jsonschema` into the shared toolchain interpreter. Without these the gates produced
  false `ToolError` failures (not skillset defects).
- Symlinked `~/.agents/node_modules → repo-A/node_modules` so the installed `duplication-audit`
  leaf can find `jscpd`. The leaf resolves jscpd at `parents[3]/node_modules/.bin/jscpd`; the
  skill install never creates a `node_modules` beside the deployed leaf, so locally the
  duplication lane silently errored (exit 2) until this was provided. CI satisfies it via
  `npm ci` on the cloned leaves. Re-running with jscpd present confirmed repo-B has no clones and
  repo-P's single duplication clone matches its accept (so it was never truly stale).

## Recommended follow-up (delivery — needs your go-ahead)

The fix and prunes are in the working tree only. To land in CI:

1. Commit the repo-B change (runner fix + regression test + accept prune) and cut a runner release
   (e.g. v0.8.2).
2. Re-pin repo-P's (and repo-B's) convergence-gate runner tag to the new release.
3. Commit repo-P's accept prune.

This is the same coordinated re-pin pattern used previously when narrowing perf-smell.

## Deferred hardening candidate (not done)

In **default mode** (no `--source-prefix`), every leaf's `_iter_python_files` still globs untracked
dependency dirs (`.venv/`, `node_modules/`). It only bites on a target repo that has a local
virtualenv. A principled fix would teach the shared file-walk to skip well-known dependency/VCS
dirs by default. Recorded as a candidate, intentionally out of scope for this dogfood (which scopes
positively via `--source-prefix`).
