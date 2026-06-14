# Exact perf-benchmark command (hold IDENTICAL for before/after)

```bash
cd /home/jakub/projects/repo-audit-skills && python3 \
  /home/jakub/projects/perf-benchmark-skill/scripts/perf_benchmark_pipeline.py \
  --root /home/jakub/projects/repo-audit-skills \
  --out-dir <OUT> \
  --target "python3 scripts/run_checks.py" \
  --tier fast --time-repeats 3 --max-cv 10.0 \
  --baseline-ledger /tmp/b0/ledger.jsonl
```

- Baseline OUT=`/tmp/b0/baseline` (p50 = 371.03s). After OUT=`/tmp/b0/after`.
- Same machine/session/governor (powersave). Fingerprint keys must match:
  cpu_model, kernel, governor, smt, python_version — all identical (same box).
- PB exit is 1 on powersave (rubric not all-green); the summary JSON is still valid.
- verify_win: `--min-win 5.0`, `--suite-exit-code` from a clean `npm run check`
  (coverage gate green), `--ledger /tmp/b0/ledger.jsonl`.
