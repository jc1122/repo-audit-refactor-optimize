# B0 candidate decision (measure-then-decide)

**Date:** 2026-06-14 · **Spec:** `../specs/2026-06-14-phase2-b0-audit-budget-perf-design.md` · **Decision rule:** spec §6

## Measured attribution

**Per-gate** (`check-timings-baseline.json`, `npm run check` on `feat/phase2-b0`, GREEN):

| gate | seconds |
|------|---------|
| coverage (`check_coverage_gap.py`) | 182.7 |
| pytest (`check_full_pytest.py`) | 175.1 |
| all 10 cheap gates (concurrent) | < 2.5 |
| **heavy total** | **357.8** |

**Per-suite** (`per-suite-timings.json`, serial), top of 20:

| seconds | suite |
|---------|-------|
| **183.69** | `skills/test-redundancy-triage/tests` |
| 13.45 | `skills/quality-audit/tests` |
| 7.58 | `tests` |
| 5.33 | `skills/test-effectiveness-audit/tests` |
| … | (remaining 16 suites total ≈ 28s) |
| **236.9** | serial total |

**Within `test-redundancy-triage` (183.7s)** — per-file: `test_inprocess_main.py` 75.1s (5 in-process `main()` runs), `test_golden.py` 75.0s (class-scoped fixtures running `main()` 1–2× each), `test_cli_smoke.py` 28.0s (class-scoped CLI run). 22 tests across 3 files ≈ 178s. All use `tmp_path`/`tmp_path_factory` (xdist-safe). Fixture-scope is **already optimized** (golden uses `scope="class"`, comment: "run main() only once… avoiding repeated ~50s subprocess invocations") — the remaining cost is **genuine pipeline work**, not redundant recomputation.

## Shares

- **double-run share** = 175.1 / 357.8 = **0.49** (the suite is run in full twice: once instrumented, once clean).
- **long-pole share** = 183.69 / 236.9 = **0.78** (`test-redundancy-triage` single-handedly floors both gates' wall time).

## Candidate evaluation

| candidate | mechanism | est. result | total wall after | risk |
|-----------|-----------|-------------|------------------|------|
| **C1 (selected)** | drop the redundant uninstrumented full-pytest gate | removes the 2nd full run | **~183s** (coverage only) | loses "tests pass uninstrumented" signal (practically negligible) |
| C2 | scoped `pytest-xdist` on `test-redundancy-triage` | speeds both gates, but safe `--dist loadscope` floors the in-process class at ~100s; keeps BOTH gates | ~200s | new dep; flakiness under parallel subprocess+coverage; lower total than C1 |
| C3 | longest-processing-time suite scheduling | one suite dominates → ordering can't help | ~358s | none, but ceiling ≈ 0 — **dead** |
| C4 | `COVERAGE_CORE=sysmon` | coverage overhead is only ~5s | ~353s | sub-threshold — **no-win** |

## Decision: **C1**

The spec §6 rule fires on its **first branch**: double-run share ≈ 0.49 **AND** the uninstrumented-green signal is acceptable to drop. Reasoning:

1. **Lowest total wall + simplest.** C1 → ~183s (one gate), beating even C2's ~200s (two faster gates), with zero new dependency, deterministic timing, and no flakiness. C3 is dead (one suite floors everything); C4 is sub-threshold.
2. **The removed work is genuinely redundant, not a designed safeguard.** The coverage gate already runs all 20 suites and **fails the run on any suite `rc != 0`** (`check_coverage_gap.py:187-190`). The full-pytest gate has **no committed baseline ratchet** — it only re-checks `rc != 0` and writes an *informational* `full_pytest_snapshot.json`. The recorded "dual gate semantics" (`references/verification.md`) concerns the **convergence-gate** accept.json mechanism (Tier-1 wave vs repo-A self-audit), **not** the coverage-vs-pytest heavy-gate pair — so dropping the second run undoes **no documented decision**.
3. **The lost signal is practically nil.** The only thing unique to the plain gate is "tests pass *without* coverage instrumentation." coverage.py (sys.monitoring/settrace) does not change test outcomes; no test in the suite today depends on an inactive tracer (both gates currently pass). If such a test were added later, the coverage gate would correctly catch it.

**Implementation:** Task 3-C1 of `../plans/2026-06-14-phase2-b0-audit-budget-perf.md`. Verified via identical perf-benchmark re-measure + `verify_win.py` (≥5% median, suite green) — expected median win ≈ 49%.
