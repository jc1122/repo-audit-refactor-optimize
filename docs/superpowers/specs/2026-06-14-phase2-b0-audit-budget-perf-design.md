# Phase 2 · B0 — bring the family's full audit under budget (perf-benchmark self-application #1)

**Status:** design (brainstorming output) · **Date:** 2026-06-14 · **Branch:** `feat/phase2-b0` (per repo)
**Campaign:** Self-Contained Convergent Skill Family — Phase 2, prerequisite item B0
**Roadmap home:** `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md` §"Phase 2 — full-pass self-application campaign"

---

## 1. Why B0 exists (and why the roadmap text is stale)

Phase 1 shipped the deterministic Tier-1 convergence wave (9 lanes incl. `perf-smell`) across the three
family repos, all CI-green. Phase 2 layers the **slow / artifact Tier-2 lanes** (`coverage-gap`,
`test-audit-pipeline` / `test-quality-assurance` / `test-redundancy-triage`, `test-effectiveness`,
`perf-benchmark` / `perf-optimization`) onto the family as a self-application campaign. Those lanes can
only be dogfooded reliably if the family's **own** audit already runs comfortably under budget — otherwise
every Tier-2 experiment fights the wall clock. B0 is that gating perf fix, and it is the family's **first
self-application of `perf-benchmark` + `perf-optimization`**.

### Stale text to correct (roadmap line 331)

> ~~"B0 (prerequisite): fix the 300s **bootstrap-probe timeout**. Profile the **8-lane wave** / the 220-test
> `test-redundancy-triage` suite…"~~

This is wrong on two counts, verified against the code on 2026-06-14:

1. **There is no bootstrap probe.** The only `300` second timeout in the path is
   `scripts/check_coverage_gap.py:147` — the `subprocess.run(..., timeout=300)` around the **coverage-gap
   leaf audit** that consumes `coverage.json` after the suites run. The per-suite coverage runs use
   `SUITE_TIMEOUT = 600`. No probe of any kind exists.
2. **The wave is 9 lanes, and the wave is not the bottleneck.** The Tier-1 convergence wave is FAST
   (per the campaign memo). The actual cost lives in **repo-A's `npm run check`** gate runner.

### The real, measured bottleneck (repo-A, `scripts/check_timings.json`, 2026-06-14)

| gate     | script                        | elapsed |
|----------|-------------------------------|---------|
| coverage | `scripts/check_coverage_gap.py` | **188.5 s** |
| pytest   | `scripts/check_full_pytest.py`  | **183.4 s** |
| all cheap gates (10) | concurrent | < 2.5 s |

Budgets (`scripts/check_budget.json`): `coverage = 270`, `pytest = 260`. Not yet over budget, but with the
Tier-2 lanes layered on top of the same suites the headroom evaporates — B0 buys that headroom back.

**Structural finding (the lever):** repo-A runs its **entire test suite twice** — once under coverage
instrumentation (`check_coverage_gap.py`, all 20 suites, `pytest --cov`) and once clean
(`check_full_pytest.py`, the same 20 suites, plain `pytest`). Coverage instrumentation adds only ~5 s
(188.5 vs 183.4), so coverage overhead is NOT the cost — the cost is **running the suites at all, twice**.
Both gates already parallelise across suites with `ThreadPoolExecutor(max_workers = cpu_count - 1)`.

**Redundancy detail (load-bearing for candidate selection):** `check_full_pytest.py` has **no committed
baseline ratchet** — it only returns non-zero when a suite's `returncode != 0` and writes an *informational*
`full_pytest_snapshot.json`. `check_coverage_gap.py` **already fails the run** if any suite's `returncode
!= 0` (lines 187–190) *and* ratchets coverage-gap findings against the committed
`scripts/coverage_gap_baseline.json`. So the plain `pytest` gate's pass/fail signal is **already covered**
by the coverage gate; the only thing unique to the plain gate is "do the tests pass *without* coverage
instrumentation" (a small defence-in-depth signal) plus its informational snapshot.

---

## 2. Goal & success criteria (falsifiable)

B0 is **measure-then-decide**. Success is one of two honest outcomes, both acceptable:

- **(A) Verified win:** a perf-benchmark baseline + after artifact shows the family-audit wall time
  (coverage + pytest) improved, the improvement clears the `perf-optimization` acceptance ratchet
  (`verify_win.py`: median wall-time win ≥ `--min-win` with no noise tier, stable environment
  fingerprint, no rubric tier drop, and the family test suite still green), and if the change touches a
  shipped repo it ships green through the Phase-1 pipeline.
- **(B) Honest no-win:** the same baseline + after artifact shows no candidate cleared the ratchet; the
  no-win is recorded per `perf-optimization/references/optimization-playbook.md` and the budgets/headroom
  are documented as-is. No change is shipped.

Either way B0 is **done** when: baseline saved, exactly one bounded candidate measured identically,
verdict recorded (accept or honest no-win), perf-smell-narrowing decision recorded, and the stale roadmap
text corrected.

---

## 3. Scope guardrails (hard)

- **Exactly ONE bounded win.** Profile, pick the single highest-ceiling bounded candidate the evidence
  supports, apply it, re-measure. Do **not** chain multiple optimisations or broadly restructure the gate
  harness. If the chosen candidate fails the ratchet, record the honest no-win — do **not** fall through
  to a second candidate in the same B0 pass (a second candidate is a new spec).
- **No new convergence semantics churn beyond the one candidate.** Removing/altering a gate is permitted
  *only if* it is the selected single candidate and its correctness tradeoff is explicitly accepted here.
- **perf-smell-narrowing is OUT of B0** (see §7) — it is a coordinated multi-repo change off the B0
  critical path.
- **Convergence-gate CI checkout keeps `fetch-depth: 0`** if any CI file is touched (hotspot/growth mine
  git history; shallow → stale accepts → red gate).

---

## 4. Measurement methodology — perf-benchmark self-application #1

This is the first time `perf-benchmark` profiles the family itself, so the methodology is part of the
deliverable.

**Two-layer evidence:**

1. **Deterministic attribution (primary, cheap):** `scripts/run_checks.py` already records per-gate
   elapsed seconds to `scripts/check_timings.json`. That answers "coverage vs pytest vs cheap." For the
   missing intra-gate question — *which suite is the long pole?* — collect per-suite wall time once (a
   throwaway timing harness around `_run_one_suite` / `run_suite`, or `pytest --durations`), because with
   `ThreadPoolExecutor` the gate wall time is floored by the **slowest single suite** once the worker
   slots saturate. The roadmap names `test-redundancy-triage` (the heaviest, ~220-test) as the suspected
   long pole — confirm or refute with data, do not assume.
2. **Ratchet envelope (perf-benchmark + perf-optimization):** wrap the family-audit workload with
   `perf-benchmark` to get `wall_time_percentiles.p50`, a stable CV (`--max-cv` gates timing noise to
   `N/A (noise)`, which `verify_win.py` rejects), an environment fingerprint, and an append-only ledger.
   Run the **same target string** before and after (the candidate changes the gate *scripts*, not the
   benchmark command), `--tier fast`, identical config, same machine/governor.

**Benchmarked target (candidate-agnostic):** the real user-facing cost, i.e. the heavy-gate workload as
`npm run check` runs it. Concretely benchmark `python3 scripts/run_checks.py` (writes `check_timings.json`
as a side artifact = free attribution) **or**, if a tighter signal is wanted, the specific heavy gate the
candidate targets. Pick one target and hold it fixed across before/after.

**`verify_win.py` inputs:** `--before` / `--after` the two `benchmark_summary.json` files; `--suite-exit-code`
= the family test suite's green status from a clean run (e.g. `check_full_pytest.py` rc, or the coverage
gate rc) so the verdict proves the win did not break tests; `--min-win` = default 5.0 unless the plan
justifies otherwise; `--ledger` the appended baseline ledger. Accept ⇒ verdict `accept` (exit 0).

**Cost note:** each heavy-gate rep is ~185 s, so a multi-rep before/after is minutes, not seconds. Keep
reps minimal (the workload is long and low-variance, so few reps give a stable p50) and `--tier fast`.

---

## 5. Candidate bounded wins (enumerated — selection deferred to the profile)

Listed highest-ceiling first. **Selection happens after profiling**, against the §6 decision rule. None is
pre-committed here.

- **C1 — Eliminate the redundant second test run.** The plain `pytest` gate re-runs all 20 suites purely
  for a pass/fail the coverage gate already enforces, with no baseline ratchet of its own (§1). Dropping
  or folding it removes ~183 s (~49 % of the 372 s) at the cost of the small "tests pass *uninstrumented*"
  defence-in-depth signal and the informational snapshot. **Ceiling: ~183 s.** Risk: it is the most
  "structural" candidate; permitted only as the single selected win, with the correctness tradeoff
  explicitly accepted, and only if no suite behaves differently under coverage (coverage.py does not
  change test outcomes in practice; the coverage gate already catches any instrumented failure). If
  selected, the cheapest faithful form is to keep an uninstrumented signal without a full second pass
  (e.g. a single combined `pytest` invocation, or accept coverage-as-the-green-gate) — the plan decides
  the exact faithful form.
- **C2 — Parallelise within the long-pole suite.** If one suite (e.g. `test-redundancy-triage`) dominates
  wall time while other cores idle at the tail, give that suite intra-suite parallelism
  (`pytest -n auto`, pytest-xdist). **Ceiling: long-pole_time − long-pole_time/cores.** Cost: adds an
  xdist dependency (pyproject + CI), and risks CPU oversubscription against the outer `ThreadPoolExecutor`
  — must be scoped so total workers don't exceed cores.
- **C3 — Longest-processing-time suite scheduling.** Zero-dependency, zero-semantics: reorder the `SUITES`
  / `suite_dirs()` lists longest-first so the `ThreadPoolExecutor` starts the long pole immediately and
  keeps cores busy. **Ceiling: bounded by the gap between current ordering and optimal packing** — small
  if one suite dominates the whole wall time, larger if the tail is several medium suites finishing
  staggered. Lowest risk.
- **C4 — `COVERAGE_CORE=sysmon` (py3.12+ sys.monitoring coverage).** Cut coverage instrumentation overhead
  on the coverage gate. **Ceiling: ~5 s** (188.5 − 183.4) — below a 5 % win on a 372 s base. Almost
  certainly a **no-win**; measure to confirm, do not select unless the profile surprises us.

---

## 6. Decision rule (deterministic)

1. Run the profile (§4 layer 1). Attribute the 372 s: double-run share vs long-pole-suite share vs
   evenly-spread.
2. Select the **single** candidate with the highest evidence-backed ceiling that stays inside the §3
   guardrails:
   - double-run dominates and the uninstrumented-green tradeoff is acceptable ⇒ **C1**;
   - one suite is the clear long pole and C1's tradeoff is judged too structural ⇒ **C2** (if the xdist
     dependency is acceptable) else **C3**;
   - cost is evenly spread with no single high-ceiling lever ⇒ apply **C3** if it clears the ratchet, else
     record an **honest no-win**.
3. Apply the one candidate. Re-measure identically (§4 layer 2). Feed `verify_win.py`.
4. `accept` ⇒ ship (§ below). `reject` / sub-threshold ⇒ **honest no-win**, revert the change, record per
   the playbook. Do **not** try a second candidate in this B0 pass.

---

## 7. perf-smell-narrowing — DECISION: DEFER (record, do not execute in B0)

The standing candidate (`repo-audit-skills/docs/superpowers/SP15-CANDIDATES.md`, last bullet): narrow
`perf-smell-audit` from the whole perflint `W81–W84 / R81–R82` range to its advertised high-precision
subset, to cut the 77 family-wide accepts (repo-B 43 + repo-P 34) of over-approximation suppression and
improve convergence honesty.

**Decision: DEFER from B0.** Rationale:

- **It is not on the B0 critical path.** B0's wall-clock floor is repo-A's coverage + pytest gates. The
  perf-smell *lane* runs inside the Tier-1 wave, which is already FAST; narrowing it does **not**
  materially move the 372 s. (It improves convergence *honesty*, a different objective.)
- **It violates the §3 "one bounded win, no broad restructure" guardrail.** It is a coordinated multi-repo
  change: re-version the repo-A leaf → re-pin repo-B/repo-P gate tags → prune stale accepts → reconverge →
  update leaf tests. That is its own spec/ship cycle, not a B0 sub-step.

**Action:** sharpen the SP15-CANDIDATES.md bullet to explicitly state B0 considered and deferred it (with
the "not on the wall-clock critical path; needs its own coordinated multi-repo spec" reasoning), so the
decision is recorded and discoverable. If later pursued it gets its own brainstorm → plan → ship.

---

## 8. Shipping (only if the win touches a shipped repo)

The likely-touched repo is **repo-A** (the gate scripts live there). Ship via the Phase-1 pipeline, order
**repo-A → repo-B → repo-P**, honouring every Phase-1 lesson:

- Branch `feat/phase2-b0` per repo; never detached HEAD.
- repo-A version bump = `package.json` + all 19 `SKILL.md`; dated CHANGELOG (date == commit date);
  read back via `git show HEAD:<file>` after the bump.
- If any repo-B/repo-P content changes, follow their conventions (repo-B SKILL.md, dateless CHANGELOG;
  repo-P SKILL.md, dated CHANGELOG; run `ruff format --check scripts/ tests/` locally before pushing
  repo-P).
- Convergence-gate CI files keep `fetch-depth: 0`.
- Verify the gate in **real CI** (`gh run watch` / `gh run list --branch main`) on every push — never
  trust a piped local exit code; read the gate JSON `status`/`active`/`stale`.
- Fresh-clone / CI sim before push; `npm ci` in fresh worktrees.
- repo-A growth re-baselines to the NEW tag only AFTER push — tag, then confirm growth green.

**If the win is repo-A-local and does not change leaf-skill behaviour** (e.g. a gate-runner-only change in
`scripts/`), a version bump is still required because repo-A's release gate ratchets on tracked changes —
the plan confirms the minimal correct bump.

If the outcome is an **honest no-win**, nothing ships; only docs (this spec's outcome note + the roadmap
correction + SP15-CANDIDATES note) change, on `feat/phase2-b0`.

---

## 9. Definition of Done (B0 only — do NOT start B1–B4)

- [ ] perf-benchmark **baseline** artifact saved (per-gate + p50 + ledger) attributing the ~372 s.
- [ ] Exactly one bounded candidate applied and **re-measured identically**; `verify_win.py` verdict
      recorded (`accept` with median win, or `reject`/sub-threshold → honest no-win recorded per the
      playbook).
- [ ] If `accept` and the change touches a shipped repo: shipped via Phase-1 pipeline; **all three mains
      CI-green incl. the `convergence-gate` job**; bumped + tagged + `gh release` + reinstalled; CHANGELOG
      read back.
- [ ] perf-smell-narrowing **decision recorded** (DEFER) in `SP15-CANDIDATES.md`.
- [ ] Roadmap **B0 text corrected** (no "bootstrap-probe", "8-lane"; real bottleneck = coverage +
      full-pytest double run over the suites; wave is 9-lane and fast).
- [ ] Memory updated; **STOP** (B1–B4 get their own specs later).

---

## 10. Self-review (planner)

- **Placeholders:** none — every candidate, threshold, and path is concrete.
- **Internal consistency:** §1 measured numbers (188.5 / 183.4) drive §5 ceilings and §6 selection; the
  "double run is redundant" finding (§1) is the basis for C1 being highest-ceiling and is backed by the
  verified no-baseline-ratchet fact.
- **Scope:** single implementation plan — profile, one candidate, verify, conditional ship. perf-smell
  narrowing and B1–B4 are explicitly excluded.
- **Ambiguity:** the win is intentionally *not* pre-selected (measure-then-decide); §6 makes the selection
  deterministic given the profile, so execution is unambiguous once data exists. Both accept and no-win are
  first-class done-states, removing "must find a win" pressure that would corrupt the measurement.
