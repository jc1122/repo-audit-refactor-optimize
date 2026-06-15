# Phase 3 · C1 — `test-audit-pipeline` umbrella: gate the `-n` flag on xdist availability

**Date:** 2026-06-15
**Item:** Phase-3 C1 (see `docs/superpowers/PHASE3-LAUNCH-PROMPT.md` §C1, recorded in
`docs/superpowers/b2-evidence/triage.md` Lane 3)
**Repo touched:** repo-A `repo-audit-skills` (`skills/test-audit-pipeline/`) — a **shipped leaf** →
ships a repo-A release.

## Problem

`skills/test-audit-pipeline/scripts/audit_pipeline.py`'s coverage stage (`stage_coverage`,
~line 134) builds the pytest command unconditionally with the `pytest-xdist` flag:

```python
cmd = [runtime.python, "-m", "pytest", "-m", config.test_marker,
       "-n", "0", f"--cov={cov_source}", "--cov-branch",
       f"--cov-report=json:{cov_json}", "-q"]
```

`-n` is provided by `pytest-xdist`. The family repos (repo-A/B/P) do **not** install xdist, so the
coverage stage fails with `error: unrecognized arguments: -n` (exit 4) — while the TQA and triage
stages succeed. B2 Lane 3 recorded this: the umbrella runs end-to-end except the built-in coverage
stage, which assumes xdist is present.

`-n 0` means "explicitly disable xdist distribution" — it is **only** meaningful (and only a valid
flag) when xdist is installed. When xdist is absent, default pytest already runs serially in-process,
so the flag is redundant there and should simply be omitted.

## Goal / falsifiable DONE

- The umbrella's coverage stage runs end-to-end on a family suite with **xdist absent** (no
  `unrecognized arguments: -n`); coverage stage reports `ok` and writes a real `coverage.json`.
- When xdist **is** present, the command still passes `-n 0` (force-serial behavior preserved — no
  silent change to parallel execution).
- repo-A ships **v0.7.4** (the umbrella is a shipped leaf), CI-green incl. convergence-gate +
  coverage-gap gate; repo-B/repo-P **unaffected** (the umbrella is a Tier-2 lane, not in the wave or
  the coverage-gap gate; no pin bump).

## Design

Two new module-level helpers in `audit_pipeline.py`, and `stage_coverage` rewired to use them.

### 1. `_xdist_available(python: str) -> bool` (detector)

Probe the **target** interpreter (`runtime.python`, which `--python` may point at a different venv
than `sys.executable`) for the `xdist` plugin module:

```python
def _xdist_available(python: str) -> bool:
    """Return True if the target interpreter can import the xdist plugin."""
    probe = "import importlib.util, sys; " \
            "sys.exit(0 if importlib.util.find_spec('xdist') else 1)"
    try:
        result = subprocess.run(
            [python, "-c", probe], capture_output=True, text=True,
        )
    except (OSError, ValueError):
        return False
    return result.returncode == 0
```

- Probes `runtime.python` (correct under `--python` overrides) — **not** the in-process interpreter.
- **Failure-safe:** any launch failure (missing interpreter, OS error) → `False` → omit `-n`
  (the safe, behavior-equivalent default).

### 2. `_build_coverage_cmd(...) -> list[str]` (pure builder)

Extract the command construction into a pure, side-effect-free function so the `-n` gating is unit
testable without running pytest:

```python
def _build_coverage_cmd(
    python: str, test_marker: str, cov_source: str, cov_json: Path,
    *, xdist_available: bool,
) -> list[str]:
    cmd = [python, "-m", "pytest", "-m", test_marker]
    if xdist_available:
        cmd += ["-n", "0"]
    cmd += [f"--cov={cov_source}", "--cov-branch",
            f"--cov-report=json:{cov_json}", "-q"]
    return cmd
```

### 3. `stage_coverage` rewired

`stage_coverage` calls `_xdist_available(runtime.python)`, then `_build_coverage_cmd(...,
xdist_available=...)`. When xdist is absent it logs one line for observability
(`"xdist not available — running coverage serially (omitting -n)"`) and omits `-n`.

## Testing (TDD, existing leaf convention)

The leaf's tests load the module via `helpers.load_module()` (the repo-A convention — orthogonal to
C3) and import helpers from `tests/helpers.py`. New tests in a focused module
`tests/test_audit_pipeline_coverage_cmd.py`:

1. `test_build_coverage_cmd_omits_n_without_xdist` — `_build_coverage_cmd(..., xdist_available=False)`
   → `"-n"` **not** in the returned list; `--cov=…`, `--cov-branch`, `--cov-report=json:…`, `-q`,
   `-m <marker>` all present.
2. `test_build_coverage_cmd_includes_n_with_xdist` — `xdist_available=True` → the consecutive
   `["-n", "0"]` pair **is** present (and exactly once).
3. `test_xdist_available_false_for_bogus_interpreter` — `_xdist_available("/nonexistent/python")`
   returns `False` (failure-safe).
4. `test_xdist_available_matches_current_env` — `_xdist_available(sys.executable)` equals
   `importlib.util.find_spec("xdist") is not None` (detector reflects reality; in CI xdist is absent
   → `False`).

These are red-first (helpers don't exist yet), then made green by the implementation. The existing 60
tests must stay green.

## Approaches considered / rejected

- **B — in-process `find_spec("xdist")`:** simpler (no subprocess) but **wrong** when `--python`
  points at a different venv than the pipeline's own interpreter. Rejected for correctness.
- **C — new `--coverage-workers` flag** to optionally parallelize coverage: scope creep / YAGNI; the
  defect is purely the unconditional `-n`. Rejected. Keep `-n 0` (serial) semantics; just gate it.

## Ship plan (repo-A release; per Phase-1 pipeline)

Leaf behaviour changed (coverage stage now works without xdist), but this leaf is **not** in the
wave or the coverage-gap gate, so **no repo-B/repo-P pin bump**. repo-A release only:

1. Branch `feat/phase3-c1` off `main`.
2. Implement + TDD (subagent-driven-development, two-stage review).
3. Bump `package.json` `0.7.3 → 0.7.4`, **all 19** leaf `SKILL.md` version strings, dated
   `CHANGELOG.md` (date == commit date = 2026-06-15).
4. `npm run check` green locally; merge to `main`; **tag `v0.7.4`**; confirm growth green post-tag.
5. `gh release create v0.7.4`; reinstall via
   `node bin/install-repo-audit-skills.js --dest ~/.claude/skills --force`.
6. Verify repo-A CI green in REAL CI (`gh run watch`) incl. convergence-gate + coverage-gap gate.
7. repo-B/repo-P: confirm still green (no change pushed); their pins stay `v0.7.2`.

## Non-goals

- No xdist dependency added (hard or optional).
- No change to TQA/triage stages, the report, or the CLI surface.
- No change to repo-B/repo-P (their gates do not use this leaf).
