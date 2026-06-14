# B2 triage — terminal decisions for the test-* lanes on the family

Measured 2026-06-15 (py3.14.4, coverage 7.14.1). All three Tier-2 test lanes were run on the
family's own suites; this file records the **terminal decision** for every finding. These lanes are
**advisory** (no binary gate), so findings land here — **not** in `.repo-audit/accept.json` (a
non-wave-lane accept would be flagged *stale* by the report-stage wave partition → RED gate, per B1).

## Lane 1 — test-quality-assurance (TQA), honest invocation (`--cov-json` with `--branch`)

| repo | total | Assert | Behav-First | Contract | Cov/Mut | Determ | Non-Func | Pyramid | White-Box |
|------|-------|--------|-------------|----------|---------|--------|----------|---------|-----------|
| repo-A | 9/24 | 1 | 0 | 1 | 1 | 2 | 1 | 2 | 1 |
| repo-B | 10→**11**/24 | 1→**2** | 0 | 1 | 1 | 3 | 1 | 2 | 1 |
| repo-P | 11/24 | 1 | 0 | 1 | 2 | 2 | 2 | 2 | 1 |

**Per-dimension terminal decision** (every <3 dimension classified):

- **Behavior-First Focus 0/3** (private/public ratio A 23 / B 68 / P 16) — **ARTIFACT, justified.**
  The family's units are CLI/script modules whose *internal functions are the unit under test*
  (`ev._load_expected`, `findings._extract_*`). Direct calls to those are correct white-box testing,
  not a smell; TQA counts them as white-box only because these modules export no package-level public
  API to baseline against. No action.
- **Contract Coverage 1/3** ("no public call hints") & **White-Box Justification 1/3** ("high
  internal coupling") — **ARTIFACT, same root cause** (script modules, no package `__init__`
  exports). We deliberately did **not** fabricate `--public-hint` values to inflate the score. No
  action.
- **Coverage/Mutation** — scope-sensitive: repo-P 2/3 (statement 88.5 %, branch 72.1 %); repo-B 1/3
  (statement 80.7 %, the top-level `tests/` suite does not exercise every script); repo-A 1/3
  (statement 34.8 % — the coverage.json spans the whole imported tree incl. leaf scripts the
  top-level `tests/` does not cover). **ARTIFACT of aggregate scoping**, not a defect; per-file
  testedness is already enforced by the **coverage-gap** lane (B1, converged at 0). No action.
- **Non-Functional 1/3** ("no benchmark markers") — **ARTIFACT**; these are correctness suites, not
  micro-benchmarks (repo-P already shows 1 marker → 2/3). N/A by design. No action.
- **Assertion Quality 1/3** — the **one GENUINE, bounded** gap (low `pytest.raises` `match=` ratio).
  **ACTED:** see Lane 4.

## Lane 2 — test-redundancy-triage (TRT), default (non-strict) gate, tractable targets

| repo | target | DELETE | MERGE_RECOMMENDED | KEEP | baseline_pass |
|------|--------|--------|-------------------|------|---------------|
| repo-A | `skills/coverage-gap-audit/tests/` (4 files) | **0** | 11 (all `MERGE_CANDIDATE`) | 0 | True |
| repo-B | `tests/test_run_instruction_eval.py` | **0** | 17 (all `MERGE_CANDIDATE`) | 0 | True |
| repo-P | `perf-optimization/tests/test_select_candidate.py` | **0** | 16 (all `MERGE_CANDIDATE`) | 3 | True |

**Terminal decision: KEEP all — 0 safe DELETE (honest no-reduction).** Every MERGE row is
`MERGE_CANDIDATE` tier with note "overlap strong but **delete gates not fully satisfied**" and
`manual_signoff_needed=False`; they are structural overlaps between **parametrize-style variants**
(e.g. `test_compute_ratio_normal` / `_zero_threshold`) that are clearer kept separate. None passes a
confident DELETE gate, so — per the conservative rule (act only on a strict-gate-passing DELETE that
keeps the suite + coverage-gap re-audit green) — **no test is removed**. This matches B0's finding
that the heavy `test-redundancy-triage` suite carries genuine, non-redundant pipeline work.

**Bonus target excluded:** the 183 s `test-redundancy-triage` suite (the wall-clock long pole) is
**impractical** to feed to TRT — TRT re-runs the target suite many times for deselection + mutation,
so running it on a 183 s suite would cost hours. Recorded, not a gap.

## Lane 3 — test-audit-pipeline (umbrella demo, repo-B)

Ran the umbrella on `tests/test_run_instruction_eval.py`: **TQA + triage stages `ok`**, unified
`pipeline_report.md` produced. **The built-in coverage stage `failed`** — it invokes
`pytest ... -n 0 ...` (pytest-xdist) which the family repos do not install →
`error: unrecognized arguments: -n` (exit 4). **Finding (recorded, deferred):** the umbrella assumes
`pytest-xdist` is present; it should gate the `-n` flag on xdist availability (or declare the dep).
This is a **shipped-leaf** change (repo-A `skills/test-audit-pipeline/`) beyond B2's test-only scope
— a candidate for its own brainstorm→plan→ship. The two underlying leaves (TQA, TRT) already run
cleanly standalone (Lanes 1–2), and honest coverage is available via the B1 subprocess-capture
recipe, so this does not block B2.

## Lane 4 — the one genuine, bounded improvement (applied)

Added `match=` to the **five** error-path `pytest.raises(ValueError)` in
`tests/test_run_instruction_eval.py`, each pinning a **stable contract message** from
`scripts/run_instruction_eval.py` (`"neither an int nor an existing file"`, `"not an int payload"`,
`"must be an int or"`, `"file does not exist"`, `"must be a JSON array"`). **Result:** repo-B TQA
Assertion Quality **1/3 → 2/3** (raises-with-match ratio 0.308 → 0.5), total **10 → 11**; 18 tests
green.

**Explicitly declined (recorded):** a **wholesale `match=` sweep** of pre-existing tests across the
family is **low-value churn / rubric-chasing** and is **not** done. repo-P's only bare raises are
`pytest.raises(SystemExit)` (argparse exit codes — `match=` on an exit code adds no contract value),
so repo-P gets **no change**; repo-A's pre-existing raises are out of scope as churn.

## Convergence statement

All three test-* lanes ran on all three family repos; every finding has a terminal decision
(structural TQA dims **justified**; TRT **0 safe DELETE → KEEP**; the umbrella xdist gap **recorded
+ deferred**; Assertion Quality **closed** for repo-B). No `.repo-audit/accept.json` change; **no
release** (test-only). Gate **graduation** of any test-* lane is **B4's** decision.
