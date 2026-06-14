# Phase 2 · B3 — test-effectiveness (mutation) on a hot module per repo

**Status:** design (brainstorming output) · **Date:** 2026-06-15 · **Branch:** `feat/phase2-b3` (repo-B)
**Campaign:** Self-Contained Convergent Skill Family — Phase 2, Tier-2 item B3
**Roadmap home:** `docs/superpowers/plans/2026-06-14-self-contained-convergent-family.md` §"Phase 2"
**Launch protocol:** `docs/superpowers/PHASE2-TIER2-LAUNCH-PROMPT.md` §3 (B3 scope & DONE)

---

## 1. Why B3 exists

Coverage (B1) answers *"is this line executed by a test?"*. Mutation (B3) answers the harder
question *"would a test actually **catch** a bug here?"*. `test-effectiveness-audit` wraps
**mutmut 3.6.0**: it sandboxes a copy of the target module + its tests, generates mutants, runs the
tests against each, and emits a `TEST` finding for any module whose **kill rate < 0.8**. B3 runs it
advisory on **one hot module per family repo** (picked by git churn), records the kill rate +
surfaced gaps, and records a close-or-accept decision per repo.

---

## 2. Methodology finding (load-bearing — discovered during measurement)

mutmut 3.x has **two hard requirements** that determine which family modules are even
mutation-testable. Both were hit empirically on 2026-06-15:

1. **No `spec_from_file_location`.** mutmut instruments source via a runtime "trampoline"; a test
   that loads the module from a file path (`importlib.util.spec_from_file_location`) bypasses the
   trampoline → *"tests recorded trampoline hits but none match any mutant key"* → mutmut aborts.
2. **The test's import dotted-path must equal mutmut's mutant key** = the module's path **from the
   sandbox source root**. A test that does `sys.path.insert(<root>/scripts); from pkg.mod import x`
   imports `pkg.mod` while mutmut keys the mutant `scripts.pkg.mod` → mismatch → abort.

**Consequence for the family** (each measured):

| repo | candidate hot module | test import style | mutation-testable? |
|------|----------------------|-------------------|--------------------|
| repo-B | `scripts/mine_iteration_kpis.py` (churn 9) | `import scripts.mine_iteration_kpis` | **YES, natively** (key matches) |
| repo-P | `scripts/perf_benchmark/ledger.py` | `from perf_benchmark.ledger import …` (sys.path→scripts) | yes, with **path-aligned staging** (key mismatch fixed) |
| repo-A | every leaf module | `helpers.load_module()` → `spec_from_file_location` (**94 test files**) | **NO** — convention-blocked |

So **repo-A is, by its own deliberate test convention, not natively mutation-testable** — the
`helpers.load_module` / `spec_from_file_location` pattern (chosen so leaves are testable without
packaging/installation) is fundamentally incompatible with mutmut 3.x. This is B3's headline finding
for repo-A, parallel to B1's subprocess-coverage and B2's pytest-xdist findings.

**Sandbox staging (how the leaf is driven for B1/B2-style isolation):** the leaf copies only the
`--paths` files + the whole `--tests-dir` into a sandbox. To avoid pulling sibling-importing tests,
each target is run from a minimal `/tmp` staging root containing just the module + its dedicated
test (no source mutated in-place — the leaf sandboxes a copy; the real repos are untouched).

---

## 3. Measured results (the data that drives the decisions)

| repo | module | kill rate | verdict | survivors |
|------|--------|-----------|---------|-----------|
| repo-B | `mine_iteration_kpis.py` | **0.671** (< 0.8) | finding | 10, **all in `_build_parser`** |
| repo-P | `perf_benchmark/ledger.py` | **≥ 0.8** (0 findings) | CLEAN | — |
| repo-A | (none runnable) | — | **BLOCKED** | n/a (convention) |

**repo-B survivor analysis (every one classified):** all 10 surviving mutants are in the argparse
builder `_build_parser`, and **all 10 are equivalent mutants**:

- `mutmut_13`, `_101`, `_104`: **remove a `help=` string** (help text does not affect parsing);
- `mutmut_107/108/109/110/111/112`: **mutate help-string text** (`XX`-prefix, lower/UPPER-case of
  the `--repo-name` help) — no behavioral effect;
- `mutmut_103`: **remove `default=None`** from `--start-sha` — argparse already defaults to `None`,
  so this is behaviorally identical.

None represents a real behavioral test gap; killing them would require asserting exact help-text
strings (brittle, tests documentation not behavior). The module's **behavioral** logic (the defaults
that matter, types, dests) is otherwise fully killed.

---

## 3a. Verified pre-check (de-risking the repo-B decision)

Two behavioral parser-contract tests (assert every `parse_args([])` default + an all-flags-set
parse) were trialed on the staged copy. They **kill the behaviorally-meaningful parser mutants**
(e.g. a mutation of `default=0`/`Path(".")`/the baseline string) but move the kill rate only
0.671 → **0.70**, because the residual 10 are the equivalent help-string mutants above. This
confirms: the genuine gap (parser defaults never asserted) is real and closeable; the residual is
provably equivalent.

---

## 4. Goal & success criteria (falsifiable)

B3 is **measure → decide (close real gaps / accept equivalents) → record**. DONE when **all** of:

1. A mutation report is committed to `b3-evidence/` for **each** repo: repo-B (kill rate +
   survivor classification), repo-P (CLEAN), repo-A (the convention-blocked finding + reproduction).
2. **repo-B:** the two parser-contract tests are added to `tests/test_mine_iteration_kpis.py` (a
   genuine regression guard that kills the behavioral parser mutants); the **residual equivalent
   help-string mutants are ACCEPTED** with the §3 classification recorded. Suite green; re-measured
   kill rate recorded (~0.70, residual = equivalents).
3. **repo-P:** CLEAN (kill ≥ 0.8) recorded; **no action**.
4. **repo-A:** the mutmut-incompatibility finding recorded with the reproduction (the
   `spec_from_file_location`/key-mismatch errors) and the decision **ACCEPT** (the limitation is
   inherent to the testability-without-packaging design; a convention change is logged as a future
   candidate, not done in B3).
5. No source mutated in-place (the leaf sandboxes a copy). Test-only repo-B change → **no release**.
   Memory updated; proceed to **B4**.

---

## 5. Scope guardrails (hard)

- **One hot module per repo**, picked by churn; bounded via `--max-mutants` and a `/tmp` staging
  root (no in-place mutation; the leaf sandboxes).
- **No production-source changes.** Only repo-B `tests/` (+ `b3-evidence/`). No `SKILL.md`/version/
  CHANGELOG → **no release** (L13).
- **No equivalent-mutant chasing.** Do **not** add brittle help-text assertions to force kill rate
  to 0.8 — that is gaming an advisory metric. Accept classified equivalents with rationale.
- **No rewriting repo-A's 94-file test convention** to chase a mutation number — out of scope;
  recorded as a future candidate.
- **Convergence-gate CI keeps `fetch-depth: 0`** (untouched — B3 edits no CI file).

---

## 6. Convergence model

Mutation is an **advisory** lane with no binary gate, so — exactly as B1/B2 — findings land in
committed `b3-evidence/`, **not** `.repo-audit/accept.json` (a non-wave-lane accept would be flagged
*stale* by the report-stage wave partition → RED gate). The repo-B "accept the equivalents" is a
documented engineering judgment in evidence, not an accept.json entry. Gate graduation of the
mutation lane (it is slow and convention-sensitive) is **not** proposed — B3 explicitly recommends
it stay Tier-2 advisory (input for B4).

---

## 7. Shipping (expected: test-only, no release)

- repo-B: add two parser-contract tests → merge `feat/phase2-b3` → `main`, no bump, no release;
  pre-merge pinned-jscpd wave-gate sim (B1-proven) + CI green incl. `convergence-gate`.
- repo-P, repo-A: **no change** (clean / blocked) — evidence only, committed to repo-B.

---

## 8. Definition of Done (B3 only)

- [ ] `b3-evidence/` holds a mutation report for **each** repo (repo-B kill-rate + survivor
      classification; repo-P CLEAN; repo-A convention-blocked finding + reproduction).
- [ ] repo-B `tests/test_mine_iteration_kpis.py` gains the two parser-contract tests; suite green;
      re-measured kill rate + equivalent-mutant acceptance recorded.
- [ ] repo-P CLEAN recorded (no action); repo-A ACCEPT + future-candidate recorded.
- [ ] No `.repo-audit/accept.json` change; no release; repo-B CI-green incl. `convergence-gate`.
- [ ] Memory updated; proceed to **B4** (do not stop).

---

## 9. Self-review (planner)

- **Placeholders:** none — every kill rate, survivor id, module, and command is measured/concrete.
- **Internal consistency:** §2's two mutmut constraints explain §3's per-repo testability; §3's
  survivor classification drives §4.2's close-real-accept-equivalent decision; §3a's pre-check
  de-risks it; §6 reuses B1/B2's verified close-not-accept / wave-stale analysis.
- **Scope:** one module per repo; one genuine test addition (repo-B); two honest non-actions
  (repo-P clean, repo-A blocked); no release. Bounded.
- **Ambiguity:** "kill rate" is mutmut's killed/total; "equivalent mutant" is defined by the §3
  classification (help-string text + behaviorally-redundant `default=None`); "close" = the two
  behavioral parser tests, not help-text assertions.
- **Anti-gaming:** B3 explicitly refuses to chase the 0.8 threshold with brittle help-text
  assertions or by rewriting repo-A's convention; it records the honest classification instead.
- **Risk:** a parser-contract test asserting a wrong default → caught by the targeted run; the
  staged-harness sys.path tweak for repo-P is a measurement accommodation (only the import line;
  test logic unchanged) and is documented in the evidence.
