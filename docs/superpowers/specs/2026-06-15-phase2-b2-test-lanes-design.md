# Phase 2 · B2 — test-* lanes on the family suites (quality + redundancy convergence)

**Status:** design (brainstorming output) · **Date:** 2026-06-15 · **Branch:** `feat/phase2-b2` (per repo)
**Campaign:** Self-Contained Convergent Skill Family — Phase 2, Tier-2 item B2
**Roadmap home:** `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md` §"Phase 2"
**Launch protocol:** `docs/superpowers/PHASE2-TIER2-LAUNCH-PROMPT.md` §3 (B2 scope & DONE)

---

## 1. Why B2 exists

B1 brought the `coverage-gap` lane onto the family and converged it. B2 brings the **test-quality
Tier-2 lanes** — `test-quality-assurance` (TQA, an 8-dimension TDD rubric, 0–24), `test-redundancy-
triage` (TRT, empirical DELETE/KEEP/MERGE), and the `test-audit-pipeline` umbrella that orchestrates
coverage + TQA + TRT — onto the family's **own** test suites, triages their findings to a terminal
state, and records the convergence.

These are **advisory** lanes (no binary gate). "Converge" therefore means: the lanes **run** on
every family repo, every finding is **triaged to a terminal decision** (closed / accepted-with-
reason / recorded-no-action), any suite change keeps every repo **green in real CI**, and the
reports are committed as evidence. The launch protocol flags a **bonus** if redundancy reductions
make the (heaviest) `test-redundancy-triage` suite faster.

---

## 2. Measured reality (the data that drives the design)

Measured 2026-06-15 (py3.14.4). This is **measure-then-decide**: the design follows the data, and
the honest finding is that the family suites are **already well-curated**.

### 2.1 TQA rubric (static, fast)

| repo | tests-dir | naive total | with `--cov-json` |
|------|-----------|-------------|-------------------|
| repo-A | `tests` | 9/24 | — |
| repo-B | `tests` | 10/24 | **11/24** |
| repo-P | `tests`,`perf-optimization/tests` | 10/24 | — |

The sub-3 dimensions are **dominated by structural artifacts of testing script-style leaf modules**,
not genuine defects:

- **Behavior-First Focus 0/3** ("private/public ratio 68.0") and **White-Box Justification 1/3**
  ("high internal coupling"): the family's units *are* CLI/script modules whose **internal
  functions are the unit under test** (`ev._load_expected`, `findings._extract_*`). Calling them
  directly is correct white-box testing, not a smell. TQA counts every `_private()` call as
  white-box because these modules export no package-level public API to baseline against.
- **Contract Coverage 1/3** ("no public call hints"): same root cause — script modules, not a
  package with `__init__` exports.
- **Coverage/Mutation 1→2/3**: lifts when `--cov-json` is passed (repo-B "Statement 85.2% ≥ 85%");
  the residual gap is **branch** coverage 0 % because the B1 recipe ran `coverage run` *without*
  `--branch`. Adding `--branch` to the recipe is the honest fix (§4).
- **Non-Functional 1/3** ("no benchmark markers"): the suites are correctness tests, not micro-
  benchmarks; N/A by design.
- **Determinism/Isolation 3/3**, **Pyramid/Scope 2/3**: already good.

The **one genuinely actionable, bounded** dimension is **Assertion Quality** (1/3, "low raises-with-
match ratio"): `pytest.raises` with a `match=` ratio of repo-A 9/48, repo-B 8/26, repo-P 0/2.

### 2.2 TRT (empirical, ~20 s for a 19-test file)

On a representative file (`perf-optimization/tests/test_select_candidate.py`, 19 tests) with the
**default (non-strict) gate**, TRT returned **0 DELETE**, 16 `MERGE_RECOMMENDED` (all
`MERGE_CANDIDATE` tier, "overlap strong but **delete gates not fully satisfied**"), 3
`KEEP_FOR_SIGNAL`. The MERGE candidates are parametrize-style variants (e.g. `test_compute_ratio_
normal` / `_zero_threshold`) that are **clearer kept separate**. This matches B0's finding that the
family suites carry **genuine, non-redundant** work. TRT is also too slow to run on the heaviest
suite (`test-redundancy-triage`'s own, the 183 s long pole — TRT re-runs the target suite many
times for deselection + mutation), so that bonus target is **impractical** and is recorded as such.

---

## 3. Goal & success criteria (falsifiable)

B2 is **run-the-lanes + honest triage**. DONE when **all** of:

1. **TQA** has run on all three repos with the **honest invocation** (§4: `--cov-json` from a
   branch-enabled coverage run), and each repo's rubric report is committed to `b2-evidence/`.
2. **TRT** has run on a **bounded, tractable** target per repo (a representative non-slow suite),
   its DELETE/MERGE/KEEP rows triaged conservatively (re-gate any removal), report committed.
3. **test-audit-pipeline** has run once (one repo) to demonstrate the umbrella on the family;
   report committed.
4. Every finding reaches a **terminal decision**, recorded in a single `b2-evidence/triage.md`:
   structural TQA dims **justified**; TRT **0 safe DELETE** recorded as an honest no-reduction;
   MERGE candidates **KEEP** with reason.
5. **One genuine, bounded quality improvement is applied** (not rubric-chasing): add `match=` to a
   **curated** set of error-path `pytest.raises` whose asserted message is a **stable contract**
   (the B1-added error-path raises in repo-B + repo-P's bare raises), lifting Assertion Quality;
   a **wholesale** `match=` sweep of pre-existing tests is explicitly **declined as low-value
   churn** and recorded as such.
6. Any suite change keeps every repo **green in real CI** (incl. `convergence-gate`); **no release**
   (test-only). Memory updated; proceed to B3.

**Honest-outcome clause:** if the curated `match=` set turns out to be empty or contrived on
inspection, B2 ships **no suite change** and records the pure-assessment outcome — that is a
legitimate terminal state, not a failure.

---

## 4. Methodology — honest lane invocation

- **TQA `--cov-json`:** regenerate each repo's `coverage.json` with the **B1 subprocess-capture
  recipe plus `--branch`** (`coverage run --branch`), so both Statement *and* Branch coverage feed
  the Coverage/Mutation dimension. Without `--branch` the dimension is capped at 2/3 by a false 0 %
  branch reading.
- **TQA scope:** `--tests-dir` per repo (repo-A `tests`; repo-B `tests`; repo-P `tests`,
  `perf-optimization/tests`). Auto public-hint inference stays **on** (default) — the honest finding
  is that script modules expose no package API, which is *why* Behavior-First/Contract score low;
  do not fabricate `--public-hint` values to inflate the score.
- **TRT target selection:** pick one representative, **fast** suite per repo (≤ ~30 s), e.g.
  repo-P `perf-optimization/tests/test_select_candidate.py`, repo-B a mid-size `tests/test_*.py`,
  repo-A one leaf's `tests/`. Default (non-strict) gate. Do **not** run TRT on the 183 s
  `test-redundancy-triage` suite (impractical; recorded).
- **Conservative removal rule:** act on a DELETE **only** if TRT marks it safe under
  `--strict-delete-gate` (mutation-probed) AND a full suite re-run + a coverage-gap re-audit stay
  green. The measured reality (§2.2) is that there are **none** at the default gate; B2 does not
  manufacture deletions.

---

## 5. Scope guardrails (hard)

- **No production-source changes.** B2 touches **test files only** (the curated `match=` additions)
  and `b2-evidence/` docs. No `SKILL.md`/version/CHANGELOG — **no release** (L13).
- **No rubric-gaming.** Improvements must be genuine (sharper assertions of a real contract), not
  mechanical churn to move a number. A wholesale `match=` sweep is out of scope and declined on the
  record.
- **No unbounded TRT.** One tractable target per repo; the slow suite is excluded by design.
- **Conservative deletions only**, re-gated; the measured default-gate reality is zero.
- **Convergence-gate CI keeps `fetch-depth: 0`** (untouched — B2 edits no CI file).

---

## 6. Convergence model (where findings "land")

These lanes are advisory and have **no** binary gate consuming their output, so — exactly as B1
decided for `coverage-gap` — their findings are **not** written to `.repo-audit/accept.json` (a
non-wave-lane accept would be flagged **stale** by the report-stage wave partition → RED gate).
Instead, B2's terminal state is recorded in committed **evidence**: the lane reports + a
`triage.md` with a per-finding decision (justified / KEEP / no-action / the one applied
improvement). Gate **graduation** of any test-* lane is — like coverage-gap — **B4's** call.

---

## 7. Shipping (expected: test-only, no release)

- repo-A, repo-B, repo-P: at most **test-file** edits (curated `match=`) → merge each
  `feat/phase2-b2` → `main`, **no** version bump, **no** release (L13). repo-P: `ruff format
  --check` + `ruff check` on changed files before push.
- repo-B (campaign home) also carries the spec, plan, and `b2-evidence/`.
- Verify real CI green (incl. `convergence-gate`) on every pushed main; pre-merge wave-gate sim with
  pinned jscpd (the B1-proven decisive check) for any repo whose tests changed.

---

## 8. Definition of Done (B2 only)

- [ ] TQA run (honest, `--cov-json --branch`) on all 3 repos; 3 rubric reports in `b2-evidence/`.
- [ ] TRT run on one tractable target per repo; 3 triage reports in `b2-evidence/`; conservative
      decisions recorded (measured: 0 safe DELETE).
- [ ] `test-audit-pipeline` run once; unified report in `b2-evidence/`.
- [ ] `b2-evidence/triage.md` records every finding's terminal decision + the wholesale-churn
      decline.
- [ ] The one curated, genuine `match=` improvement applied (or honestly recorded as empty), suites
      green, TQA Assertion Quality re-measured for the touched repo(s).
- [ ] No `.repo-audit/accept.json` change; no release. Every touched repo CI-green incl.
      `convergence-gate`.
- [ ] Memory updated; proceed to **B3** (do not stop).

---

## 9. Self-review (planner)

- **Placeholders:** none — every score, ratio, target, and command is measured/concrete.
- **Internal consistency:** §2 data drives §3 DONE and §4 methodology; §2.2's "0 safe DELETE"
  drives §5's "no manufactured deletions"; §2.1's "Assertion Quality is the one genuine gap" drives
  §3.5's single bounded improvement; §6 reuses B1's verified close-not-accept / wave-stale analysis.
- **Scope:** three advisory lanes demonstrated + honest triage + one bounded test-only improvement;
  no release; gating deferred to B4. Bounded.
- **Ambiguity:** "converge" is made concrete = lanes run + every finding terminal-decided + reports
  committed + suites green. "Genuine improvement" is bounded to error-path raises asserting a stable
  contract message; wholesale churn explicitly excluded.
- **Anti-gaming:** TQA is advisory; B2 explicitly refuses to fabricate public hints or sweep
  `match=` to inflate the rubric — it records the honest structural explanation instead.
- **Risk:** test-file `match=` edit could mis-assert a message → caught by the targeted test run +
  full-suite re-run + pinned-jscpd wave-gate sim before merge.
