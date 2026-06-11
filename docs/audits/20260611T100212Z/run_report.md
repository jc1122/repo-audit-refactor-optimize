# SP9 K3 v2 Run Report (repo-B)

- Schema version: 2
- Repo root: `/home/jakub/projects/repo-audit-refactor-optimize`
- Started UTC: 2026-06-11T10:02:12Z
- Finished UTC: 2026-06-11T11:15:50Z
- Orchestrator skill version: 0.4.0
- Baseline commit for final wave evidence: `55fa638`
- Push: no push was performed.

## Lane Summary

| Lane | Exit | Status | Findings |
|---|---:|---|---:|
| code-health | 2 | error (advisory gate residuals frozen) | 11 |
| security | 0 | ok | 0 |
| hygiene | 0 | ok | 0 |
| docs | 1 | findings | 3 |
| dependency | 0 | ok | 0 |
| hotspot | 1 | findings | 9 |

`code-health` exit 2 is retained as the advisory GATE verdict after the remaining
baseline was frozen, not treated as a crash.

## Findings

Raw final-wave signal totals:

| Signal | Count |
|---|---:|
| SIMPLIFY | 8 |
| DECOMPOSE | 3 |
| RESTRUCTURE | 6 |
| FORMAT | 2 |
| DELETE | 1 |
| LINT | 3 |
| SECURITY | 0 |
| TEST | 0 |

Leaf totals:

| Leaf | Count |
|---|---:|
| complexity | 8 |
| dead-code | 1 |
| docs-consistency | 3 |
| hotspot | 9 |
| quality | 2 |

Normalized baseline: `scripts/wave_baseline.json` has 23 findings.

## Final Backlog

| Class | Count |
|---|---:|
| accepted | 0 |
| deferred | 17 |
| coverage_gated | 0 |
| wont_fix | 6 |

Frozen-log summary: 23 total = 17 deferred-structural + 6 won't-fix-FP.
Coverage-gated and accepted-mechanical buckets are both 0.

Expiry buckets:

| Expires | Count |
|---|---:|
| v0.5.0 reinstall | 6 |
| v0.5.0 convergence review | 8 |
| post-v0.5.x decomposition | 9 |

## K3 Task Evidence

| Task | Commits | Result |
|---|---|---|
| K3-T1 | `4f8331b`, `769b02a`, `7695c70`, `da1cc59` | Decomposed `check_skill_requirements.py` into `_skill_probe`, `_lane_resolve`, and `_bootstrap_report` with public re-exports. T1 suite reached 88 passed. D1-D7 cleared where test-compatible; public signature/module residuals are frozen. |
| K3-T2 | `3172db6` | Added `scripts/validate_run_report.py` and `tests/test_validate_run_report.py`. Historical schema v1 command returned `{"status":"pass"}`. Suite reached 93 passed. |
| K3-T3 | `4b08fea` | Added `scripts/run_diagnosis_wave.py` and `tests/test_run_diagnosis_wave.py`. Stub-leaf tests passed; suite reached 96 passed. Final line count after hardening is 248. |
| K3-T4 | `5f46f39` | Updated taxonomy v2, run-report v2, docs-repair docs, `SKILL.md` version 0.4.0, and `CHANGELOG`. `SKILL.md` line count is 114, under 160. Suite reached 96 passed; `check_release` returned `{"status":"pass"}`. |
| K3-T5 | `53f0881`, `9ca316c`, `55fa638` | Added `check_wave_baseline.py` and tests, cleared mechanical/security findings, seeded `scripts/wave_baseline.json` and `scripts/wave_frozen.md`, and ignored `.wave_out/`. Final line counts: `run_diagnosis_wave.py` 248, `check_wave_baseline.py` 83, `validate_run_report.py` 114. |

## Line Counts

| File | Lines |
|---|---:|
| `SKILL.md` | 114 |
| `scripts/run_diagnosis_wave.py` | 248 |
| `scripts/check_wave_baseline.py` | 83 |
| `scripts/validate_run_report.py` | 114 |

## Verification

| Command | Exit | Output |
|---|---:|---|
| `python3 -m pytest tests/ -q` | 0 | `100 passed` |
| `python3 -m pytest --collect-only -q` | 0 | `100 tests collected` |
| `python3 scripts/check_release.py` | 0 | `{"status":"pass"}` |
| `WAVE_RUNNER=$PWD/scripts/run_diagnosis_wave.py SKILLS_ROOT=$HOME/.claude/skills python3 scripts/check_wave_baseline.py` | 0 | wave summary: code-health 11, security 0, hygiene 0, docs 3, dependency 0, hotspot 9; `{"status":"pass","count":23,"baseline":23}` |
| `python3 ~/.claude/skills/security-audit/scripts/security_audit.py --root . --out-dir /tmp/sp9-k3-accepted-security --source-prefix scripts` | 0 | `{"status":"ok","findings":0,"leaf":"security"}` |
| `python3 ~/.claude/skills/code-health-audit-pipeline/scripts/code_health_pipeline.py --root . --out-dir /tmp/sp9-k3-accepted-health --source-prefix scripts` | 2 | `{"status":"ok","supervisor":"GATE","findings":11,...}`; advisory gate residuals now frozen |
| `python3 scripts/validate_run_report.py --run-dir docs/audits/20260611T061957Z --schema 1` | 0 | `{"status":"pass"}` |
| `python3 scripts/validate_run_report.py --run-dir docs/audits/20260611T100212Z` | 0 | `{"status": "pass"}` |
| `git diff --check` | 0 | empty output |

## Warnings

1. `code-health` exit 2 is the expected advisory GATE residual state after the final backlog freeze, not a crash.
2. Remaining final backlog is frozen in `scripts/wave_frozen.md`: 17 deferred-structural, 6 won't-fix-FP, 0 coverage-gated, 0 accepted-mechanical.
3. `performance` lane remains manual because no benchmark surface was part of the K3 wave.
4. Coverage-gated count is 0 because the final backlog carries SECURITY 0 and TEST 0.
5. No push was performed.
