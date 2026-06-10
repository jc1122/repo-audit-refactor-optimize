# Remediation Playbook

Maps every finding signal from the shared code-health finding schema (repo-audit-skills) to a safe execution procedure. This replaces generic refactoring/code-style guidance: the *diagnosis* is deterministic, the *execution* below is the discipline for acting on it.

## Standing Rules

1. **Coverage gate first.** Before touching a file, check the coverage lane's TEST findings. Uncovered file → characterize-first: write behavior/golden tests for the current contract, get them green, then remediate. No exceptions for "obvious" changes.
2. **One signal class per batch.** Never mix mechanical lint fixes with structural moves in one commit; verification cannot attribute regressions.
3. **Ratchet.** Re-run the producing leaf after each batch. Findings may only shrink; growth means stop and investigate before the next batch.
4. **Tests green before and after** every batch, on the smallest sufficient surface first, full relevant suite before closing the batch.
5. **Goldens are contracts.** If a remediation changes observable output and a golden test catches it, investigate and explain; never silently regenerate a golden to make a fix pass.

## Signal Procedures

| Signal | Emitted by | Meaning | Procedure |
|---|---|---|---|
| `LINT` | quality-audit | Lint violation | Fix mechanically in bulk per file. Prefer `ruff check --fix` for auto-fixable codes; review non-auto-fixable ones individually (late-binding/`B023`-class findings are real bug risks — fix deliberately, watch goldens). |
| `FORMAT` | quality-audit | Formatting drift | Apply the formatter (`ruff format`) to the flagged files only. Zero logic review needed; keep the batch purely mechanical. |
| `TYPE` | quality-audit | Type-check error | Fix the annotation or the code, never silence with blanket ignores. A per-line ignore requires an inline reason. |
| `DELETE` | dead-code-audit | Unused code | Confirm reachability (grep for dynamic uses: getattr, registries, entry points, tests). Then delete outright — no commenting out. One module per batch. |
| `MERGE` (same file) | duplication-audit | In-file clone | Extract a local helper only if it nets fewer findings (params, length). If extraction trades one finding for another, keep the clone and justify. |
| `EXTRACT` (cross file) | duplication-audit | Cross-file clone | Only extract into a shared module when the files may legitimately import a common dependency. Vendored/standalone tools must stay self-contained — record a justified freeze instead. |
| `SIMPLIFY` | complexity-audit | High cyclomatic complexity / long function | Reduce branching via early returns, dict dispatch, or guard clauses. If the function is a cohesive linear pipeline (parse → transform → emit), splitting may relocate, not reduce — justify keeping it. |
| `DECOMPOSE` | complexity-audit | Oversized function/module, too many params | Group parameters into a dataclass or split by responsibility. Check the result against the producing leaf before committing: helpers with 5+ params or new clones are regressions. |
| `RESTRUCTURE` | structure-audit | Import cycle / god module | Break cycles by extracting the shared dependency downward (never by inline imports as a permanent fix). For god modules, split by fan-in clusters. Highest-risk class: always characterize-first even in covered files if the public surface is unclear. |
| `TEST` | coverage-gap-audit | Untested / under-tested file | Not a refactor license. Add behavior tests for the file's JSON/stdout/exit-code contract (in-process where coverage tracing requires it) until the file clears the threshold, or record a concrete justification. |
| `PERF` | perf-benchmark | Failing perf rubric dimension | Follow the perf-benchmark skill's references/perf-remediation-playbook.md: algorithmic STOP gate, one dimension per batch, >=5% median win within CV bounds, before/after fingerprints must match. |

## Batch Protocol

1. Pick the top-ranked batch from the prioritized backlog (one signal class, one or few files).
2. Coverage gate (rule 1). 3. Apply the signal procedure. 4. Run the file/module tests, then the full relevant suite.
5. Re-run the producing leaf; confirm the finding count for the batch scope shrank and nothing new appeared elsewhere.
6. Commit with the signal class and finding count delta in the message. 7. Rebaseline before the next batch.

## Stop Conditions

Stop the execution phase and report instead of continuing when: a batch grows total findings; a golden changes without an explained behavior change; two consecutive batches make no net progress; or remediation requires changing a public contract (needs explicit human approval).
