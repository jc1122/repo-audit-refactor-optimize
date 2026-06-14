# B1 coverage-gap recipe (reproducible)

Subprocess-capture coverage is **mandatory** — a plain `coverage run -m pytest` only instruments
the parent process, so subprocess-tested CLIs are falsely reported as 0 % covered. Measured proof
(repo-P): `perf-optimization/scripts/verify_win.py` shows **0 %** plain vs **96 %** with capture;
`select_candidate.py` 39.8 % → 95.9 %. Only `scripts/perf_benchmark/findings.py` (imported
in-process) was a true gap under either method.

## Hook (once per machine/session)
```bash
mkdir -p /tmp/b1/cov-hook
printf 'import coverage\ncoverage.process_startup()\n' > /tmp/b1/cov-hook/sitecustomize.py
```
`sitecustomize.py` on `PYTHONPATH` runs in every child Python; `coverage.process_startup()`
activates only when `COVERAGE_PROCESS_START` is set. Tests must inherit the parent env
(`subprocess.run(...)` with no `env=` override) for this to propagate — verified true for repo-P's
`test_verify_win.py` / `test_select_candidate.py`.

## repo-A (verify-only — already gated at 0)
```bash
cd ~/projects/repo-audit-skills
python3 scripts/check_coverage_gap.py --coverage-json .self_audit_out/coverage/coverage.json
# -> {"status":"pass","count":0,"baseline":0}
```
repo-A's gate scope is `check_coverage_gap._prefixes()` = `shared`, `scripts`, and each
`skills/<name>/scripts`. A too-broad `--source-prefix skills` sweeps in `tests/` and yields 183
false findings vs the true 0 — name production dirs precisely.

## repo-B (scope: scripts) and repo-P (scope: scripts + perf-optimization/scripts)
```bash
REPO=<abs repo path>; OUT=/tmp/b1/<repo>; RC=$OUT/.coveragerc
mkdir -p "$OUT"
printf '[run]\nparallel = true\ndata_file = %s/.coverage\n[report]\nignore_errors = true\n' "$OUT" > "$RC"
PYTHONPATH=/tmp/b1/cov-hook:$PYTHONPATH COVERAGE_PROCESS_START="$RC" \
  python3 -m coverage run --rcfile="$RC" -m pytest <suite dirs> -q -p no:cacheprovider
python3 -m coverage combine --rcfile="$RC"
python3 -m coverage json --rcfile="$RC" --data-file="$OUT/.coverage" -o "$OUT/coverage.json"
python3 ~/.claude/skills/coverage-gap-audit/scripts/coverage_gap_audit.py \
  --root "$REPO" <--source-prefix ...> --coverage-json "$OUT/coverage.json" --out-dir "$OUT/leaf"
# suite dirs: repo-B = "tests/"; repo-P = "tests/ perf-optimization/tests/"
```

`ignore_errors = true` is required: a subprocess may touch a non-UTF-8 *out-of-scope* fixture that
otherwise aborts `coverage json` mid-report. `parallel = true` + `coverage combine` merges the
parent's and every subprocess's `.coverage.*` shard before the JSON report.
