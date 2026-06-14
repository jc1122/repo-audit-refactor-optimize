# B1 coverage-gap convergence — before/after

Measured 2026-06-15 on this machine (py3.14.4, coverage 7.14.1), subprocess-capture coverage.

| repo | leaf scope (`--source-prefix`) | before findings | action | after findings |
|------|-------------------------------|-----------------|--------|----------------|
| repo-A | `shared`, `scripts`, `skills/*/scripts` | **0** | verify-only (gate already converged) | **0** |
| repo-B | `scripts` | **1**: `scripts/run_instruction_eval.py` 33.3 % (22/66) | +15 behaviour tests → **100 %** | **0** |
| repo-P | `scripts`, `perf-optimization/scripts` | **1**: `scripts/perf_benchmark/findings.py` 47.5 % (38/80) | +10 behaviour tests → **95.0 %** | **0** |

Artifacts in this dir: `repoA-findings.json`, `repoB-findings-after.json`,
`repoP-findings-after.json` — all `[]`.

## Methodology note — subprocess capture is mandatory

Plain (parent-only) coverage misreports subprocess-tested CLIs:

| repo-P file | plain | subprocess-capture | reality |
|-------------|-------|--------------------|---------|
| `perf-optimization/scripts/verify_win.py` | 0.0 % (false gap) | 96.3 % | CLI-tested via subprocess |
| `perf-optimization/scripts/select_candidate.py` | 39.8 % (false gap) | 95.9 % | subprocess + in-process |
| `scripts/perf_benchmark/findings.py` | 47.5 % | 47.5 % | the one true gap |

Plain coverage reports **3** repo-P findings (two false); subprocess capture reports the **1** true
finding. B1 used capture for honest numbers.

## Convergence decision — close, not accept

Both genuine gaps were in pure, deterministic, stdlib-only modules → closed with behaviour tests
(the strongest outcome). **No `coverage-gap` accept entries were added** to any repo:
`coverage-gap` is not a wave lane, so a `coverage-gap` accept in repo-B/repo-P's
`.repo-audit/accept.json` (default `applies` includes `report`) would match no wave finding and be
flagged **stale** by the report-stage wave partition (`_accept.AcceptPolicy.partition` →
`check_wave_baseline._converge`), turning the convergence gate RED. Closing avoids this entirely:
0 findings ⇒ `active 0`, no accepts ⇒ no stale possible. Gate **graduation** of the now-cheap lane
(coverage regenerates in ~10 s) is deferred to **B4**.

## Shipping

Test-only changes (no shipped skill content) → no version bump, no release (launch-protocol L13);
merge each branch to `main` and verify real CI green (incl. `convergence-gate`). repo-A unchanged.
