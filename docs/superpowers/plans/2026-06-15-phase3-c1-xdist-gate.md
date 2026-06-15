# Phase 3 · C1 — xdist-gate for the test-audit-pipeline coverage stage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `test-audit-pipeline` umbrella's coverage stage run without `pytest-xdist`
installed, by gating the `-n 0` flag on xdist availability in the target interpreter.

**Architecture:** Extract the coverage pytest command into a pure builder
(`_build_coverage_cmd`) parameterised on `xdist_available: bool`, and add a `_xdist_available(python)`
detector that probes the *target* interpreter via a tiny subprocess. `stage_coverage` calls the
detector then the builder, omitting `-n` when xdist is absent (behavior-equivalent: default pytest is
serial in-process). TDD the two helpers; ship a repo-A release (the umbrella is a shipped leaf).

**Tech Stack:** Python 3.14, pytest, the repo-A leaf-test convention (`helpers.load_module()` +
`tests/helpers.py`, conftest puts the test dir on `sys.path`). Spec:
`docs/superpowers/specs/2026-06-15-phase3-c1-xdist-gate-design.md`.

**Repo root for all paths below:** `/home/jakub/projects/repo-audit-skills` (repo-A). Implementation
happens on the repo-A branch `feat/phase3-c1`.

---

## Task 1: TDD the `_build_coverage_cmd` pure builder + `_xdist_available` detector, rewire `stage_coverage`

**Files:**
- Modify: `skills/test-audit-pipeline/scripts/audit_pipeline.py` (add 2 helpers near
  `stage_coverage`, ~line 126; rewire `stage_coverage` body, lines 126-154)
- Create: `skills/test-audit-pipeline/tests/test_audit_pipeline_coverage_cmd.py`

- [ ] **Step 1: Write the failing tests**

Create `skills/test-audit-pipeline/tests/test_audit_pipeline_coverage_cmd.py`:

```python
"""Tests for the xdist-gated coverage command builder + detector (Phase 3 C1)."""

import importlib.util
import sys
from pathlib import Path

from helpers import load_module

ap = load_module()


def test_build_coverage_cmd_omits_n_without_xdist():
    cmd = ap._build_coverage_cmd(
        python="py", test_marker="not slow", cov_source="scripts",
        cov_json=Path("/tmp/cov.json"), xdist_available=False,
    )
    assert "-n" not in cmd
    assert cmd[:5] == ["py", "-m", "pytest", "-m", "not slow"]
    assert "--cov=scripts" in cmd
    assert "--cov-branch" in cmd
    assert "--cov-report=json:/tmp/cov.json" in cmd
    assert cmd[-1] == "-q"


def test_build_coverage_cmd_includes_n_with_xdist():
    cmd = ap._build_coverage_cmd(
        python="py", test_marker="not slow", cov_source="scripts",
        cov_json=Path("/tmp/cov.json"), xdist_available=True,
    )
    # exactly one consecutive ["-n", "0"] pair
    i = cmd.index("-n")
    assert cmd[i + 1] == "0"
    assert cmd.count("-n") == 1


def test_xdist_available_false_for_bogus_interpreter():
    assert ap._xdist_available("/nonexistent/python-xyz") is False


def test_xdist_available_matches_current_env():
    expected = importlib.util.find_spec("xdist") is not None
    assert ap._xdist_available(sys.executable) is expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/jakub/projects/repo-audit-skills/skills/test-audit-pipeline && python3 -m pytest tests/test_audit_pipeline_coverage_cmd.py -q`
Expected: FAIL — `AttributeError: module 'audit_pipeline' has no attribute '_build_coverage_cmd'`
(and `_xdist_available`).

- [ ] **Step 3: Add the two helpers**

In `skills/test-audit-pipeline/scripts/audit_pipeline.py`, immediately **before** `def
stage_coverage(` (currently ~line 126, after the `# Stage 1: Coverage collection` banner), insert:

```python
def _xdist_available(python: str) -> bool:
    """Return True if the target interpreter can import the xdist plugin.

    Probes ``python`` (which may differ from ``sys.executable`` under
    ``--python``); any launch failure is treated as "absent" so the caller
    omits the xdist-only ``-n`` flag.
    """
    probe = (
        "import importlib.util, sys; "
        "sys.exit(0 if importlib.util.find_spec('xdist') else 1)"
    )
    try:
        result = subprocess.run(
            [python, "-c", probe],
            capture_output=True,
            text=True,
        )
    except (OSError, ValueError):
        return False
    return result.returncode == 0


def _build_coverage_cmd(
    python: str,
    test_marker: str,
    cov_source: str,
    cov_json: Path,
    *,
    xdist_available: bool,
) -> list[str]:
    """Build the coverage pytest command, gating ``-n`` on xdist availability.

    ``-n 0`` is a ``pytest-xdist`` flag (force-serial). When xdist is absent it
    is invalid and pytest exits 4; default pytest is already serial in-process,
    so the flag is simply omitted there (behavior-equivalent).
    """
    cmd = [python, "-m", "pytest", "-m", test_marker]
    if xdist_available:
        cmd += ["-n", "0"]
    cmd += [
        f"--cov={cov_source}",
        "--cov-branch",
        f"--cov-report=json:{cov_json}",
        "-q",
    ]
    return cmd
```

- [ ] **Step 4: Rewire `stage_coverage` to use the helpers**

Replace the body of `stage_coverage` (the `cmd = [ ... ]` literal, currently lines ~134-146) so the
function reads:

```python
def stage_coverage(
    runtime: StageRuntime,
    config: CoverageConfig,
) -> tuple[bool, Path]:
    """Collect branch coverage with pytest-cov. Returns (success, json_path)."""
    cov_json = runtime.out_dir / "coverage.json"
    cov_source = config.source_prefix if config.source_prefix else str(runtime.root)

    xdist_available = _xdist_available(runtime.python)
    if not xdist_available:
        _log("  · xdist not available — running coverage serially (omitting -n)")
    cmd = _build_coverage_cmd(
        runtime.python,
        config.test_marker,
        cov_source,
        cov_json,
        xdist_available=xdist_available,
    )
    result = _run_stage(cmd, env=runtime.env, cwd=runtime.root, label="coverage")
    if result.returncode != 0:
        _log(f"  ✗ Coverage collection failed (exit {result.returncode})")
        if result.stderr:
            _log(result.stderr[:2000])
        return False, cov_json
    _log("  ✓ Coverage collected")
    return True, cov_json
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `cd /home/jakub/projects/repo-audit-skills/skills/test-audit-pipeline && python3 -m pytest tests/test_audit_pipeline_coverage_cmd.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Run the full leaf suite (no regression)**

Run: `cd /home/jakub/projects/repo-audit-skills/skills/test-audit-pipeline && python3 -m pytest tests/ -q`
Expected: PASS — 64 passed (60 existing + 4 new).

- [ ] **Step 7: Integration check — the coverage stage runs end-to-end without xdist**

Confirm xdist is absent, then run the umbrella's coverage stage against this leaf's own suite:

```bash
cd /home/jakub/projects/repo-audit-skills/skills/test-audit-pipeline
python3 -c "import importlib.util; assert importlib.util.find_spec('xdist') is None, 'xdist unexpectedly present'"
python3 scripts/audit_pipeline.py --root . --out-dir /tmp/c1-pipe \
    --skip-triage --source-prefix scripts \
    --test-marker "not benchmark and not slow"
echo "exit=$?"
python3 -c "import json; d=json.load(open('/tmp/c1-pipe/pipeline_summary.json')); print('coverage stage:', d['stage_status']['coverage'])"
```
Expected: pipeline exits 0; `stage_status['coverage'] == 'ok'`; a real `/tmp/c1-pipe/coverage.json`
is written (no `unrecognized arguments: -n`).

- [ ] **Step 8: Commit**

```bash
cd /home/jakub/projects/repo-audit-skills
git add skills/test-audit-pipeline/scripts/audit_pipeline.py \
        skills/test-audit-pipeline/tests/test_audit_pipeline_coverage_cmd.py
git commit -m "fix(test-audit-pipeline): gate coverage -n flag on xdist availability

The coverage stage hardcoded pytest-xdist's -n 0; family repos don't install
xdist so the stage failed (exit 4). Probe the target interpreter and omit -n
when xdist is absent (behavior-equivalent: default pytest is serial)."
```

---

## Task 2: repo-A release bump (v0.7.3 → v0.7.4)

**Files:**
- Modify: `package.json` (line 3, `"version"`)
- Modify: **all 19** `skills/*/SKILL.md` (line 3, `version:`)
- Modify: `CHANGELOG.md` (prepend new entry)

- [ ] **Step 1: Bump package.json**

In `/home/jakub/projects/repo-audit-skills/package.json` change line 3 from
`  "version": "0.7.3",` to `  "version": "0.7.4",`.

- [ ] **Step 2: Bump all 19 leaf SKILL.md version strings**

Run:
```bash
cd /home/jakub/projects/repo-audit-skills
grep -rl '^version: 0.7.3$' skills/*/SKILL.md | xargs sed -i 's/^version: 0.7.3$/version: 0.7.4/'
grep -rc '^version: 0.7.4$' skills/*/SKILL.md | grep -c ':1' # expect 19
```
Expected: `19`. Verify none left at 0.7.3: `grep -rl '^version: 0.7.3$' skills/*/SKILL.md` → empty.

- [ ] **Step 3: Prepend the CHANGELOG entry**

Insert directly under the `# Changelog` header in `/home/jakub/projects/repo-audit-skills/CHANGELOG.md`
(date == commit date = 2026-06-15):

```markdown
## 0.7.4 - 2026-06-15

Phase 3 C1: fixed the `test-audit-pipeline` umbrella's coverage stage, which hardcoded
`pytest-xdist`'s `-n 0` flag and failed (exit 4, `unrecognized arguments: -n`) on the family
repos that do not install xdist. The stage now probes the target interpreter and only passes
`-n 0` when the xdist plugin is importable; otherwise it omits the flag (behavior-equivalent —
default pytest runs serially in-process). No xdist dependency added; TQA/triage stages and the
CLI surface are unchanged. The umbrella is a Tier-2 advisory lane (not in the convergence wave or
the coverage-gap gate), so repo-B/repo-P pins are unaffected.
```

- [ ] **Step 4: Verify the bump via git-show-style read-back**

Run:
```bash
cd /home/jakub/projects/repo-audit-skills
node -e "console.log('pkg', require('./package.json').version)"      # 0.7.4
grep -rl '^version: 0.7.4$' skills/*/SKILL.md | wc -l                # 19
head -3 CHANGELOG.md                                                 # shows 0.7.4 - 2026-06-15
```

- [ ] **Step 5: Commit the release bump**

```bash
cd /home/jakub/projects/repo-audit-skills
git add package.json skills/*/SKILL.md CHANGELOG.md
git commit -m "chore(release): family 0.7.3 -> 0.7.4 (Phase 3 C1 test-audit-pipeline xdist gate)"
```

---

## Post-implementation (orchestrator-driven; NOT subagent tasks)

The orchestrator (not a worker) performs, after Task 2, in order:
1. `npm run check` green locally (incl. convergence-gate + coverage-gap gate simulated).
2. Merge `feat/phase3-c1` → `main` (no-ff), push.
3. **Tag `v0.7.4`**, push the tag; confirm growth lane green post-tag.
4. `gh release create v0.7.4`.
5. Reinstall: `node bin/install-repo-audit-skills.js --dest ~/.claude/skills --force`.
6. Verify repo-A CI green in REAL CI (`gh run watch`), reading the gate JSON.
7. Confirm repo-B/repo-P mains still green (no change pushed there); pins stay `v0.7.2`.
8. Read back every bump via `git show HEAD:<file>`.

---

## Self-review notes

- **Spec coverage:** `_xdist_available` (spec §1) → Task 1 Step 3; `_build_coverage_cmd` (spec §2) →
  Task 1 Step 3; `stage_coverage` rewire (spec §3) → Task 1 Step 4; 4 TDD tests (spec §Testing) →
  Task 1 Step 1; release v0.7.4 (spec §Ship) → Task 2 + post-impl. All covered.
- **Placeholder scan:** none — every code/command step shows full content.
- **Type consistency:** `_build_coverage_cmd(python, test_marker, cov_source, cov_json, *,
  xdist_available)` and `_xdist_available(python)` signatures are identical in spec, helper
  definition, test calls, and the `stage_coverage` call site.
