# Phase 3 · C1 — outcome (VERIFIED WIN, shipped repo-A v0.7.4)

Completed 2026-06-15. The `test-audit-pipeline` umbrella's coverage stage no longer assumes
`pytest-xdist`. Full superpowers pipeline run: spec
(`specs/2026-06-15-phase3-c1-xdist-gate-design.md`) → plan
(`plans/2026-06-15-phase3-c1-xdist-gate.md`) → subagent-driven-development (fresh implementer per
task + spec-then-quality review).

## Problem (B2 Lane 3)

`skills/test-audit-pipeline/scripts/audit_pipeline.py` `stage_coverage` hardcoded `pytest-xdist`'s
`-n 0` into the coverage pytest command. The family repos don't install xdist, so the stage failed
(`error: unrecognized arguments: -n`, exit 4) while TQA + triage stages succeeded.

## Fix

- `_xdist_available(python: str) -> bool` — probes the **target** interpreter (`runtime.python`, which
  `--python` may point at a different venv) via a bounded (`timeout=30`) subprocess running
  `importlib.util.find_spec('xdist')`; any launch failure (`OSError`/`ValueError`/`TimeoutExpired`) →
  `False` (failure-safe).
- `_build_coverage_cmd(..., *, xdist_available)` — pure command builder; includes `["-n", "0"]` only
  when xdist is available, else omits `-n` (behavior-equivalent: default pytest is serial in-process).
- `stage_coverage` rewired to use both; logs one line when xdist is absent.
- No xdist dependency added. CLI / TQA / triage stages unchanged.

## Verification (re-run by the orchestrator, not trusting worker "green")

- New leaf tests `tests/test_audit_pipeline_coverage_cmd.py` (4): builder omits `-n` w/o xdist;
  builder includes exactly one `["-n","0"]` w/ xdist; detector `False` for bogus interpreter; detector
  matches `find_spec` in the current env. Full leaf suite **64 passed** (60 existing + 4 new).
- **Integration (xdist absent, the bug scenario):** `python3 scripts/audit_pipeline.py --root .
  --out-dir /tmp/c1-pipe --skip-triage --source-prefix scripts` → pipeline exit 0; coverage stage
  `ok`; real `coverage.json` written; no `unrecognized arguments: -n`.
- `npm run check`: pre-tag only `growth` RED (count 3 = net-positive LOC, baseline v0.7.3 — expected
  per the B0 growth lesson); all other cheap gates + the coverage heavy gate green. Post-tag
  `check_growth.py` → `{"status":"pass","count":0,"baseline":"v0.7.4"}`.

## Ship (repo-A release, Phase-1 pipeline)

- Branch `feat/phase3-c1`; commits: fix (`6b0b63e`, amended w/ timeout hardening from the code-quality
  review), release bump (`cfc207f`).
- Bumped `package.json` 0.7.3→0.7.4 + **all 19** leaf `SKILL.md` + dated `CHANGELOG.md` (2026-06-15).
- Merged to `main` (`a28e682`), tagged **v0.7.4** (annotated), pushed main+tag together,
  `gh release create v0.7.4`, reinstalled leaves to `~/.claude/skills`.
- **REAL CI green** on repo-A main (`a28e682`, run 27517645267, conclusion success) — incl. growth
  (re-baselined to v0.7.4), selfaudit/convergence, and the coverage-gap gate.

## repo-B / repo-P — unaffected, no pin bump

The umbrella is a Tier-2 advisory lane: it is **not** a convergence-wave lane and **not** in the
coverage-gap gate, and repo-B/repo-P do not clone it. Their convergence-gate pins stay `v0.7.2`; no
stale accepts introduced; no push to either repo. Both mains remain green (last runs from the Phase-2
B4 / phase3-launch merges).

## Status: TERMINAL — verified win. repo-A v0.7.4 shipped + CI-green; repo-B/repo-P untouched + green.
