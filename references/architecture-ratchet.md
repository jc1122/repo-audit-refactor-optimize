# Architecture ratchet, frozen measures and replay

Use this for structural refactors at more than one-batch scale: an import
contract, a backlog of its violations, waves of tasks, and a verdict at the
end. It records what worked in METHOD BET #3428
(jc1122/agent-fleet-method#3428, 2026-10-15/16: a structural refactor of the
agent-fleet-method scripts). Every number here comes from that issue or its
artifacts (`spec.md`, `arch-measures.sh`, `.importlinter`, `semgrep.yml`,
`replay.md`, `replay-signflip.txt`, task contracts, PR #3549).

Scope rule unchanged: an audit may measure and recommend all of this. Adding a
CI gate, a contract file or a codemod to the target is an edit and needs the
user's authorization. The host dispatches, edits, posts and owns Git; this
skill never merges or schedules.

## 1. Detection goes through the CLI

| Concern | Run |
|---|---|
| Function complexity | `scan --checks complexity` |
| Change hotspots, surface growth | `scan --checks hotspot,growth` |
| Dead code | `scan --checks dead-code` |
| Copy-paste clones | `scan --checks duplication` |
| Import cycles, fan-in and fan-out | `scan --checks structure` |
| Untested predicates (executing, opt-in) | `scan --checks test-effectiveness --max-mutants N` |
| Algorithmic smells | `scan --checks perf-smell` |

Do not call the tools these checks wrap. Everything below is what the CLI
does not provide. Copy-paste tools miss semantic duplicates (the same rule
implemented twice in different ways): in #3428, jscpd found 50 duplicate lines
out of 11,391, while the reviews found 12 semantic duplicates. A semgrep rule
(section 2) forbids each one after it is deduplicated.

## 2. Architecture as code, in CI, ratchet mode

**Import contract.** Write `.importlinter` with `layers`, `independence` or
`forbidden` contracts. The #3428 draft used one layers contract plus two
independence contracts; the final contract was a single layers contract:

```ini
[importlinter]
root_package = pkg

[importlinter:contract:layers]
name = entry > controller > services > records
type = layers
layers =
    pkg.entry_a | pkg.entry_b
    pkg.controller
    pkg.service_a | pkg.service_b
    pkg.records
ignore_imports =
    pkg.records -> pkg.controller
unmatched_ignore_imports_alerting = error
```

Run `lint-imports --no-cache --config .importlinter` (exit 0 kept, 1 broken).
#3428's scripts were not an importable package, so its checker parsed the
import edges with `ast`, including deferred and `importlib` literal imports.
It wrote them into an empty temporary package and linted that package, so the
target code was never imported.

**Semgrep boundary rules.** Write one rule per boundary, in the form "only X
names layout Y; everyone else reads it through X". The #3428 rules covered a
queue directory layout, raw `sed` reads of a config file, raw grep/awk parsing
of ledgers, a registry path and redefined grammar names. Example:

```yaml
rules:
  - id: pro-layout-private
    languages: [regex]
    severity: ERROR
    message: only pro_bridge names the pro/ layout; read it through pro_bridge
    paths: {include: ["/scripts/"], exclude: ["/scripts/lib/pro_bridge.py"]}
    pattern-regex: pro/(queue|claimed|results|refused)\b
```

Run `semgrep scan --config .semgrep.yml --error --metrics=off --oss-only
$(git ls-files <dir>)`. Pass an explicit file list, because a directory target
hung semgrep 1.181 in #3428.

**Ratchet.**
- List current violations in `ignore_imports` and in a semgrep baseline of
  (rule, path, fingerprint of the whitespace-normalized match).
- New findings must be 0. The lists only shrink, and each removed line is one
  task.
- The closing task runs both checks in CI with empty lists.
- A missing analyzer fails closed (exit 2), never as a silent zero.

In #3428, import violations went 17→0, ignores 5→0 and all five semgrep rules
reached 0 (one of them from 24) by the end of wave 2.

## 3. CI complexity ratchet from day one

The CI step runs `radon cc -j $(git ls-files '<lib>/*.py')`:
- If any block is above the limit (40 in #3428), it exits 1 and prints each
  offender as `file:qualname=cc`.
- Known offenders are exempt through an inline dict of caps at their current
  values. A cap may shrink, never grow.
- A missing radon exits 2.

Land this gate with the first wave, not at the end. #3428's CI checked imports
and rules but not complexity. Task 37 cut `_close_sets` from 43 to 33, and
within hours an improver fix (#3518) raised it to 50. The `complexity` check
finds offenders; this gate keeps them from coming back.

## 4. One frozen measure script

Pin one script at the baseline, before any task lands. In #3428 this was
`arch-measures.sh`. Its analyzers were pinned in its own venv: import-linter
2.15, grimp 3.17, radon 6.0.1, vulture 2.16, semgrep 1.181.0, libcst 1.9.0.

```bash
arch-measures.sh REPO [REV] [--check 'KEY<=N']... [--drop-ignore 'pkg.a -> pkg.b']
```

- It prints `KEY=VALUE` lines: import_violations, contracts_broken,
  import_cycles, cc_max, functions_cc_over_40, vulture_items, semgrep_new,
  size and so on. `cc:FILE:QUALNAME` checks one function.
- Exit codes: 0 measured, 1 a `--check` failed, 2 an analyzer or input error.
- With a `REV` argument it measures `git archive` of that commit, so baselines
  are reproducible. #3428's baselines reproduced byte-for-byte on two commits.
- Vulture false positives go in a whitelist file of
  `PATH<TAB>MESSAGE<TAB>REASON` lines. A line without a reason is an error.
- Each task's acceptance is its `--check` lines plus the test suite. Post the
  full output on every PR and at every wave end.
- To fix the instrument, version it and re-baseline. v1 undercounted
  cycles; v2's AST edges found 2 where v1 found 1.

## 5. Measure reading cost before refactoring for tokens

Measure from the agents' own transcripts, per merged fix:
- fresh+output tokens (fresh excludes cache reads);
- repository lines read, files read and rereads;
- protocol lines (the repo's instruction and process files) and CHANGELOG
  lines.

#3428 did this with `replay-metrics.py --since TS RUN_DIR REPO`, which reuses
the reads audit's frozen parser. Its baseline over 102 merged fixes:
- a median of 1,734 repository lines and 125.5k fresh tokens per fix;
- 19.4% of read lines were protocol files;
- tokens correlated with the size of the files read (ρ = 0.71);
- with that spread, 30 fixes detect only shifts of about 15% or more.

Refactor for tokens only when this data points at structure, meaning code
reads in the modules you would restructure. If protocol or docs reads
dominate, cut those instead.

## 6. Before/after replay is the verdict

1. **Freeze first.** Freeze the protocol and the target before any structural
   task lands. #3428's target: at least 30% fewer tokens and lines per fix,
   first-try PASS on (b) ≥ (a), and wall time on (b) ≤ (a).
2. **Pick the fixes.** Choose about ten merged fixes. Each needs its own
   tests and must revert cleanly.
3. **Build the arms.** Arm (a) is the pre-refactor base plus
   `git revert --no-commit -m 1 <merge>`. Arm (b) is the post-refactor
   release plus the same revert, ported to the symbol's new home where the
   revert conflicts.
4. **Check validity.** On both arms, each item's hidden acceptance must fail
   on the base and pass on the reference. Otherwise replace the item with the
   next spare.
5. **Dispatch matched runs.** Use the same harness, model, effort, output
   limit and prompt bytes. Run 2 repetitions per item and arm, and start both
   arms of an item together.
6. **Score the pairs.** Average each item's repetitions per arm and take the
   paired ratio (b)/(a). Run an exact sign-flip test on the per-fix log
   ratios (all 2^n sign assignments; n = 7 gives 128). Report the geometric
   ratio, p and the 95% CI.
7. **Apply the harm guard.** Count first-try PASS on the hidden tests, using
   the builder's first committed candidate with no resume. (b) must be ≥ (a).

## 7. The #3428 verdict

- **Maintainability improved** (baseline 9ce53ce6 versus the task 38
  candidate in PR #3549):
  - CC max went 155→51.
  - Import violations went 17→0.
  - Cycles went 1→0 (v1 count; v2 counted 2, and both were cut).
  - Functions with CC > 40 went 13→2.
- **Reading cost did not drop** (`replay-signflip.txt`, n = 7 fixes). Paired
  geometric ratios (b)/(a):
  - tokens 1.17 (p = 0.547, 95% CI 0.68–2.04);
  - repository lines 1.16 (p = 0.562, 95% CI 0.63–2.11).
  - Builders read 20 files against 12 (medians), because the moved code now
    spans more modules.
- **Only the protocol and docs cut saved:** −54% protocol lines and −82%
  CHANGELOG lines per fix.
- **Correctness did not regress:** first-try PASS was 12/14 against 10/14.

So present structural refactors as maintenance work (contracts, cycles,
complexity, hotspot risk), not as a token saving. Refactor for tokens only
when the section 5 data points at structure.

## 8. Lessons from #3428

- Owned paths for a move include every test that names a moved symbol. `git grep` it in tests, including mutation anchors and harness copies, when shaping the task.
- Run each task's acceptance once on the base before dispatch. It must fail for its declared reason.
- Use codemods (LibCST in #3428; rope 1.15 crashed on its code under Python 3.14) for moves, and builders only for judgment.
- Have two independent reviewers review the draft, then write the final spec from their reviews.
- Sampled mutation testing (`test-effectiveness`) finds untested predicates. Classify each survivor as equivalent or real before writing tests.
- For live service cut-overs, smoke-test the client path with a model request and look for config files that shadow the new endpoint. #3428 had two outages: one from a socket-only drain check, one from a stale settings file.
