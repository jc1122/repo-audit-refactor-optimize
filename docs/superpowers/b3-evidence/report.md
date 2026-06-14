# B3 mutation-effectiveness report (one hot module per repo)

Measured 2026-06-15 (py3.14.4, mutmut 3.6.0 via `test-effectiveness-audit`). Each target ran in a
minimal `/tmp` staging root (module + its dedicated test); **no source was mutated in-place** (the
leaf sandboxes a copy). Findings recorded here — **not** in `.repo-audit/accept.json` (a non-wave-lane
accept would be flagged *stale* by the report-stage wave partition → RED gate, per B1/B2).

## Per-repo kill rates

| repo | hot module (churn) | kill rate | verdict | action |
|------|--------------------|-----------|---------|--------|
| repo-B | `scripts/mine_iteration_kpis.py` (9) | 0.671 → **0.70** | finding (residual = equivalents) | +2 parser-contract tests; accept equivalents |
| repo-P | `scripts/perf_benchmark/ledger.py` | **≥ 0.8** (0 findings) | CLEAN | none |
| repo-A | (none runnable) | — | **BLOCKED** | accept + future candidate |

## repo-B — survivor classification (all 10 equivalent)

All 10 surviving mutants are in the argparse builder `_build_parser`, and every one is an
**equivalent mutant** (no behavioral effect, unkillable without brittle help-text assertions):

- `mutmut_13`, `_101`, `_104` — remove a `help=` string (help text does not affect parsing);
- `mutmut_107/108/109/110/111/112` — mutate `--repo-name` help-string text (`XX`-prefix /
  lower-case / UPPER-case);
- `mutmut_103` — remove `default=None` from `--start-sha` (argparse already defaults to `None`).

**Decision (repo-B):** the two added tests (`test_build_parser_defaults_and_dests`,
`test_build_parser_explicit_args`) assert every parsed default + an all-flags-set parse — a genuine
regression guard that **kills the behaviorally-meaningful parser mutants** (default values, types,
dests). The kill rate moves 0.671 → 0.70 because the residual 10 are the equivalent help-string
mutants above; these are **ACCEPTED** with this classification. We deliberately do **not** add
help-text assertions to chase the 0.8 threshold — that would game an advisory metric and test
documentation, not behavior. The module's behavioral test effectiveness is complete.

## repo-P — CLEAN

`perf_benchmark/ledger.py` mutation kill rate ≥ 0.8 (0 findings) — its tests are effective at
catching mutations. **No action.** (Run via path-aligned staging: the staged test's `SCRIPTS_DIR`
was pointed at the staging root so the test's `perf_benchmark.ledger` import matches mutmut's mutant
key; only the import line was adjusted, the test logic is unchanged.)

## repo-A — BLOCKED by test convention

repo-A's leaf tests load modules via `helpers.load_module()` / `spec_from_file_location`
(**97 test files**). mutmut 3.x instruments source through a runtime trampoline that
`spec_from_file_location` bypasses, so it cannot correlate test execution with mutants. **No repo-A
module is natively mutation-testable.** **Decision: ACCEPT** — the convention is a deliberate design
choice (leaves testable without packaging/installation); a convention change is logged as a future
candidate, not done in B3. See `repoA-blocked.md` for the reproduction.

## Methodology finding (load-bearing)

mutmut 3.x mutation-testability requires **both**: (1) the test imports the module as a normal
package module (NOT `spec_from_file_location`), and (2) the test's import dotted-path equals
mutmut's mutant key = the module's path from the sandbox source root. This gates which family
modules can be mutation-tested (repo-B `mine_iteration_kpis` natively; repo-P `ledger` with
path-aligned staging; repo-A not at all under its current convention). **Recommendation:** the
mutation lane should **stay Tier-2 advisory** — it is slow and convention-sensitive, not a binary
gate candidate. (Input for B4.)

## Convergence statement

A mutation report exists for each repo; every finding is terminal-decided (repo-B close-behavioral +
accept-equivalents; repo-P no-action; repo-A accept + future candidate). No `.repo-audit/accept.json`
change; test-only repo-B change → no release.
