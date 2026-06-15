# Dogfood Gap Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every code step shows the actual code/diff — do not improvise.

**Goal:** Make the repo-audit dogfood loop's "converged / green" signal trustworthy and self-catching by closing all 11 verified gaps, so a green wave gate provably means "every lane actually ran, no accepted metric silently degraded, the deployed artifact works, and pins are coherent."

**Architecture:** Three repos. **repo-B** = `repo-audit-refactor-optimize` (the wave *runner* `run_diagnosis_wave.py`, normalization `_wave_findings.py`, accept policy `_accept.py`, and a committed copy of the convergence gate `check_wave_baseline.py`). **repo-P** = `perf-benchmark-skill` (its own committed gate; clones repo-B `@tag` as `WAVE_RUNNER` — runner is **shared by pin**). **repo-A** = `repo-audit-skills` (the 19 leaves, the installer, and repo-A's own fail-closed `run_checks.py` gate; leaves shared by pin via `git clone --branch <tag>`). Runner-side fixes are written once in repo-B and reach repo-P by **re-pin**; gate-side fixes are applied to **both** committed `check_wave_baseline.py` copies. Work is sequenced into three independently-shippable waves.

**Tech Stack:** Python 3.12/3.14 (stdlib + the pinned leaf toolchain), pytest 9 + hypothesis, jscpd (Node) for the duplication leaf, GitHub Actions, `gh` CLI for release/CI verification.

---

## Conventions (read once before starting)

- **TDD always.** Every behavioural change: write the failing test → run it, confirm it fails for the *expected* reason → minimal implementation → run, confirm pass → commit. Never write implementation before a red test.
- **Branch per wave.** `git switch -c wave-a-trustworthy-green` etc. off `main` in each touched repo. Never commit straight to `main`.
- **Commit cadence:** one commit per task (test+impl together is fine; the red/green steps are verification gates, not separate commits unless noted).
- **Run the suite from the repo root.** repo-B/repo-P: `python -m pytest tests/ -q`. repo-A: `python -m pytest tests/ -q`.
- **Commit message footer (every commit):**
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- **Versions chosen by this plan** (semver, breaking-gate-behaviour ⇒ minor bumps): repo-B `0.8.2 → 0.9.0` (Wave A) `→ 0.10.0` (Wave B); repo-P `0.4.3 → 0.5.0` (Wave A re-pin) `→ 0.6.0` (Wave C); repo-A `0.7.5 → 0.8.0` (Wave C). Each wave's ship section restates the exact bumps.
- **Deployed skill locations** (reinstall targets): `~/.claude/skills/<skill>` and `~/.agents/skills/<skill>`. Reinstall = sync the repo's skill tree to both after a release (see each ship section).
- **All three remotes are GitHub `jc1122/<repo>`.** Pushing a tag triggers CI; verify with `gh run watch` / `gh run list`.
- **Definition of Done per wave:** all three mains CI-green including the convergence gate + the new gate(s) introduced by that wave; downstream pins updated; skills reinstalled.

---

# WAVE A — Trustworthy Green (#1, #2, #9, #3, #10)

Goal of the wave: a green `check_wave_baseline.py` means every lane executed, no accepted finding's metric exceeded its recorded ceiling or expiry, no accept reason is unaudited boilerplate, and the running toolchain matches its pins.

## Task A1: Convergence gate fails on an errored lane (#1)

**Root cause:** `check_wave_baseline.py._run_wave()` calls `subprocess.run(cmd, check=False)` and **discards the returncode**; `main()` reads only `wave_findings.json` (active) + `wave_findings.accepted.json`. It never reads `wave_summary.json`. The runner already writes per-lane `status:"error"` and returns `wave_exit=1`, but the gate ignores both → an errored lane produces 0 findings → empty active set → false GREEN.

**Files (repo-B):**
- Modify: `scripts/check_wave_baseline.py`
- Modify: `tests/test_check_wave_baseline.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_check_wave_baseline.py`:

```python
def test_fail_when_a_lane_errored_even_if_active_empty(tmp_path, capsys):
    """The core #1 fix: an errored lane (0 findings) must NOT pass the gate."""
    snapshot = tmp_path / "active.json"
    accepted = tmp_path / "accepted.json"
    summary = tmp_path / "summary.json"
    _dump(snapshot, [])
    _dump(accepted, {"accepted": [], "stale": []})
    _dump(summary, {
        "security": {"exit": 2, "status": "error", "findings": 0},
        "hygiene": {"exit": 0, "status": "ok", "findings": 0},
    })

    rc = mod.main(["--snapshot", str(snapshot),
                   "--accepted", str(accepted), "--summary", str(summary)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["status"] == "fail"
    assert captured["reason"] == "lane_error"
    assert captured["errored_lanes"] == ["security"]


def test_pass_when_all_lanes_ok_and_active_empty(tmp_path, capsys):
    snapshot = tmp_path / "active.json"
    summary = tmp_path / "summary.json"
    _dump(snapshot, [])
    _dump(summary, {"security": {"exit": 0, "status": "ok", "findings": 0}})

    rc = mod.main(["--snapshot", str(snapshot), "--summary", str(summary)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "pass"
```

Also update the existing `test_run_wave_forwards_anchor_and_wave_configs`: `_run_wave()` now returns a tuple. Change its assertion block to:

```python
    out, rc = mod._run_wave()
    assert out == repo / ".wave_out"
    assert rc == 0
```
And make the fake runner write a summary + exit 0 by appending to its script body:
```python
        "(out / 'wave_summary.json').write_text('{}', encoding='utf-8')\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/projects/repo-audit-refactor-optimize && python -m pytest tests/test_check_wave_baseline.py -q`
Expected: the two new tests FAIL (`--summary` unrecognized / `reason` KeyError); the forwards test FAILs on tuple unpack.

- [ ] **Step 3: Implement the gate change**

In `scripts/check_wave_baseline.py`:

Add `--summary` to `_parse_args`:
```python
    ap.add_argument("--summary", help="read the wave summary from this file (tests)")
```

Change `_run_wave` to return `(out, returncode)`:
```python
    proc = subprocess.run(cmd, check=False)  # nosec B603: shell=False
    return out, proc.returncode
```

Add a lane-error extractor:
```python
def _lane_errors(summary):
    """Lane names whose status is 'error' (lane failed to produce a verdict)."""
    return sorted(
        name for name, info in summary.items()
        if isinstance(info, dict) and info.get("status") == "error"
    )
```

Change `_converge` signature + add the fail-closed check FIRST:
```python
def _converge(active, accepted_sidecar, lane_errors, runner_rc):
    """Option A verdict, fail-closed: any lane error or nonzero runner exit fails."""
    if lane_errors or runner_rc != 0:
        return _fail({
            "status": "fail",
            "reason": "lane_error",
            "errored_lanes": lane_errors,
            "runner_exit": runner_rc,
        })
    if active:
        return _fail({
            "status": "fail",
            "new_findings": sorted(map(list, identities(active))),
        })
    stale = list(accepted_sidecar.get("stale", []))
    if stale:
        return _fail({"status": "fail", "stale_acceptances": sorted(stale)})
    accepted = accepted_sidecar.get("accepted", [])
    _emit({"status": "pass", "accepted": len(accepted), "active": 0})
    return 0
```

Rewrite `main`:
```python
def main(argv=None):
    args = _parse_args(argv)
    if args.snapshot:
        active = _load_json(args.snapshot)
        sidecar = _load_json(args.accepted) if args.accepted else {"stale": []}
        summary = _load_json(args.summary) if args.summary else {}
        runner_rc = 0
    else:
        out, runner_rc = _run_wave()
        active = _load_json(out / "wave_findings.json")
        sidecar = _load_json(out / "wave_findings.accepted.json")
        summary = _load_json(out / "wave_summary.json")
    return _converge(active, sidecar, _lane_errors(summary), runner_rc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_check_wave_baseline.py -q`
Expected: PASS (all, including the updated forwards test).

- [ ] **Step 5: Mirror the fix into repo-P's gate**

repo-P's `scripts/check_wave_baseline.py` has a different shape (`_run_wave() -> Path`, `_wave_command`). Apply the *same semantics*:
- `_run_wave` returns `(out, proc.returncode)`.
- Add identical `_lane_errors`, `--summary` arg, and the `lane_errors or runner_rc != 0` first-check in its `_converge`/`main`.
- Add the same two tests to `perf-benchmark-skill/tests/test_check_wave_baseline.py` (adjust the module import path to repo-P's).

Run: `cd ~/projects/perf-benchmark-skill && python -m pytest tests/test_check_wave_baseline.py -q`
Expected: PASS.

- [ ] **Step 6: Commit (both repos)**

```bash
cd ~/projects/repo-audit-refactor-optimize && git add scripts/check_wave_baseline.py tests/test_check_wave_baseline.py
git commit -m "fix(gate): convergence gate fails on errored lane (#1)

Read wave_summary.json + runner exit code; an errored lane (0 findings)
no longer passes the gate via an empty active set.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
cd ~/projects/perf-benchmark-skill && git add scripts/check_wave_baseline.py tests/test_check_wave_baseline.py
git commit -m "fix(gate): convergence gate fails on errored lane (#1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task A2: Per-lane timeout watchdog (#9)

**Root cause:** `run_diagnosis_wave.py._run_lane` calls `subprocess.run(...)` with **no `timeout=`**. A misbehaving leaf (the perflint/.venv hang) blocks open-ended until the CI job timeout — not a clean lane signal.

**Files (repo-B):**
- Modify: `scripts/run_diagnosis_wave.py`
- Modify: `tests/test_run_diagnosis_wave.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_run_diagnosis_wave.py` (match its existing import style):

```python
import subprocess as _subprocess

def test_lane_timeout_becomes_error(tmp_path, monkeypatch):
    """A timed-out lane returns exit 124 -> status 'error' (caught by the gate)."""
    rdw = importlib.import_module("scripts.run_diagnosis_wave")

    def _boom(*a, **k):
        raise _subprocess.TimeoutExpired(cmd="leaf", timeout=k.get("timeout", 1))

    monkeypatch.setattr(rdw.subprocess, "run", _boom)
    ctx = rdw._LaneContext(
        repo=tmp_path, out_root=tmp_path, source_prefixes=[], exclude_prefixes=[],
        rev=None, coverage_json=None, security_config=None, hotspot_config=None,
    )
    exit_code, findings = rdw._run_lane("security", tmp_path / "leaf.py", ctx)
    assert exit_code == 124
    assert findings == []
    assert rdw._status_for_exit(124, 0) == "error"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_run_diagnosis_wave.py::test_lane_timeout_becomes_error -q`
Expected: FAIL (TimeoutExpired propagates uncaught; no 124 path).

- [ ] **Step 3: Implement**

In `scripts/run_diagnosis_wave.py`, add near the top imports:
```python
import os
```
Add a module-level helper (after the constants block):
```python
def _lane_timeout() -> int:
    """Per-lane wall-clock budget (seconds); env-overridable for tests/CI."""
    return int(os.environ.get("WAVE_LANE_TIMEOUT", "600"))
```
In `_run_lane`, change the subprocess call:
```python
    try:
        exit_code = subprocess.run(  # nosec B603: shell=False
            cmd, check=False, capture_output=True, text=True,
            timeout=_lane_timeout(),
        ).returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
    except OSError:
        exit_code = 2
    return exit_code, _wave_findings.collect_lane_findings(lane_out, lane)
```
(`_status_for_exit(124, 0)` already returns `"error"` because 124 ≥ 2 with 0 findings, and `_run_wave` already sets `wave_exit=1` for `exit_code >= 2 and not findings` — so a timeout now flows through Task A1's gate as an error. No further change needed.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_run_diagnosis_wave.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_diagnosis_wave.py tests/test_run_diagnosis_wave.py
git commit -m "fix(wave): per-lane timeout -> exit 124 -> error status (#9)

A hung leaf now becomes an errored lane (caught by the #1 gate) instead
of an open-ended hang. Budget via WAVE_LANE_TIMEOUT (default 600s).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task A3: Accepted findings carry a metric value ceiling (#2)

**Root cause:** `_wave_findings._normalize_finding` reduces `metric` to `metric.get("name")`, discarding the value/threshold (which the shared schema *requires*: `metric:{name,value,threshold}`). `identity()` is `(leaf,path,symbol,metric-name)`, so a function accepted at complexity 12 that balloons to 40 keeps its identity, stays suppressed, gate stays green. The accept policy has `expires`/`is_expired()` but partition still puts expired entries in `accepted`, and the gate ignores the `expired` annotation.

**Design:** Carry `value` *alongside* (never *inside*) the identity. An accept entry gains an optional numeric `max_value` ceiling. At partition time an entry **blocks** a finding (pushes it to the *active* set, where Task A1's gate fails on it) when the entry is **expired** OR the finding's value **exceeds** `max_value`; otherwise it accepts. A blocking entry still counts as "matched" (so it is not also reported stale — single clear failure).

### Task A3a: Normalization carries value + threshold

**Files (repo-B):** Modify `scripts/_wave_findings.py`, `tests/test_wave_findings.py`.

- [ ] **Step 1: Failing test** — add to `tests/test_wave_findings.py`:

```python
def test_normalize_carries_metric_value_and_threshold():
    raw = {"leaf": "complexity", "path": "a.py",
           "location": {"symbol": "f"},
           "metric": {"name": "cyclomatic", "value": 40, "threshold": 10}}
    norm = wf._normalize_finding(raw, "code-health")
    assert norm["metric"] == "cyclomatic"
    assert norm["value"] == 40
    assert norm["threshold"] == 10
    # identity is unchanged — value rides alongside, not inside
    assert wf.identity(norm) == ("complexity", "a.py", "f", "cyclomatic")
```

- [ ] **Step 2: Run, expect FAIL** (`KeyError: 'value'`).
  Run: `python -m pytest tests/test_wave_findings.py::test_normalize_carries_metric_value_and_threshold -q`

- [ ] **Step 3: Implement** — in `_normalize_finding`, after computing `metric`:

```python
    metric_obj = finding.get("metric")
    value = metric_obj.get("value") if isinstance(metric_obj, dict) else None
    threshold = metric_obj.get("threshold") if isinstance(metric_obj, dict) else None
    return {
        "leaf": _string_value(finding.get("leaf"), lane),
        "path": _string_value(finding.get("path"), location.get("path", "")),
        "symbol": _string_value(finding.get("symbol"), location.get("symbol", "")),
        "metric": "" if metric is None else str(metric),
        "value": value,
        "threshold": threshold,
    }
```
(`identity()` reads only the four keys, so it is unaffected.)

- [ ] **Step 4: Run, expect PASS.** Run: `python -m pytest tests/test_wave_findings.py -q`
- [ ] **Step 5: Commit** `fix(wave): carry metric value+threshold through normalization (#2)`.

### Task A3b: AcceptEntry gains `max_value` (parse + schema)

**Files (repo-B):** Modify `scripts/_accept.py`, `schema/accept.schema.json`, `tests/test_accept.py`.

- [ ] **Step 1: Failing test** — add to `tests/test_accept.py` (match its import of `scripts._accept`):

```python
def test_parse_entry_accepts_numeric_max_value():
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "x", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "accepted at 12; tracked in CHANGELOG v0.9.0",
        "max_value": 12}]}
    policy = acc._parse_policy(raw)
    assert policy[0].max_value == 12

def test_parse_entry_rejects_non_numeric_max_value():
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "x", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "r", "max_value": "twelve"}]}
    with pytest.raises(acc.AcceptError):
        acc._parse_policy(raw)
```
(`acc` = the module alias already used in that test file; if the file imports it under another name, reuse that.)

- [ ] **Step 2: Run, expect FAIL.**
  Run: `python -m pytest tests/test_accept.py -k max_value -q`

- [ ] **Step 3: Implement** in `scripts/_accept.py`:

Add field to the dataclass (last, with default so positional constructors keep working):
```python
@dataclass(frozen=True)
class AcceptEntry:
    kind: str
    fields: dict[str, str]
    reason: str
    applies: frozenset[str]
    expires: str | None
    max_value: float | None = None

    def is_expired(self, today: date | None = None) -> bool:
        ...  # unchanged

    def exceeds_ceiling(self, finding: dict[str, Any]) -> bool:
        """True when a numeric ceiling is set and the finding's value exceeds it."""
        if self.max_value is None:
            return False
        value = finding.get("value")
        try:
            return value is not None and float(value) > float(self.max_value)
        except (TypeError, ValueError):
            return False
```
In `_parse_entry`, before the `return`:
```python
    max_value = raw.get("max_value")
    _require(
        max_value is None
        or (isinstance(max_value, (int, float)) and not isinstance(max_value, bool)),
        f"accept[{index}].max_value must be number|null",
    )
    return AcceptEntry(kind, fields, reason, applies, expires, max_value)
```
In `schema/accept.schema.json`, add inside the entry `properties`:
```json
          "max_value": {"type": ["number", "null"]}
```

- [ ] **Step 4: Run, expect PASS.** Run: `python -m pytest tests/test_accept.py -q`
- [ ] **Step 5: Commit** `feat(accept): optional numeric max_value ceiling (#2)`.

### Task A3c: Partition blocks expired / ceiling-exceeded entries into the active set

**Files (repo-B):** Modify `scripts/_accept.py` (`AcceptPolicy.partition`), `tests/test_accept.py`.

- [ ] **Step 1: Failing tests** — add to `tests/test_accept.py`:

```python
def _ceiling_policy():
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "x", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "accepted at 12; CHANGELOG v0.9.0", "max_value": 12}]}
    return acc.AcceptPolicy(acc._parse_policy(raw))

def test_value_within_ceiling_is_accepted():
    f = {"leaf": "x", "path": "a.py", "symbol": "f", "metric": "cyclomatic", "value": 12}
    active, accepted, stale = _ceiling_policy().partition([f], "report")
    assert active == [] and len(accepted) == 1 and stale == []

def test_value_over_ceiling_goes_active_not_accepted():
    f = {"leaf": "x", "path": "a.py", "symbol": "f", "metric": "cyclomatic", "value": 40}
    active, accepted, stale = _ceiling_policy().partition([f], "report")
    assert len(active) == 1 and accepted == []
    assert active[0]["ceiling_exceeded"] is True
    assert active[0]["actual_value"] == 40 and active[0]["accepted_value"] == 12
    assert stale == []   # entry matched its identity target -> not stale

def test_expired_entry_goes_active_not_accepted():
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "x", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "temporary; CHANGELOG", "expires": "2000-01-01"}]}
    policy = acc.AcceptPolicy(acc._parse_policy(raw))
    f = {"leaf": "x", "path": "a.py", "symbol": "f", "metric": "cyclomatic", "value": 5}
    active, accepted, stale = policy.partition([f], "report")
    assert len(active) == 1 and accepted == []
    assert active[0]["accept_expired"] is True and stale == []
```

- [ ] **Step 2: Run, expect FAIL.** Run: `python -m pytest tests/test_accept.py -k "ceiling or expired" -q`

- [ ] **Step 3: Implement** — replace the body of `AcceptPolicy.partition`'s per-finding loop:

```python
        for finding in findings:
            hit = self._first_hit(finding, stage_entries)  # identity-only match
            if hit is None:
                active.append(finding)
                continue
            idx, entry = hit
            matched.add(idx)            # found its target -> never stale
            if entry.is_expired():
                active.append({**finding,
                               "accept_expired": True,
                               "accept_reason": entry.reason})
            elif entry.exceeds_ceiling(finding):
                active.append({**finding,
                               "ceiling_exceeded": True,
                               "accepted_value": entry.max_value,
                               "actual_value": finding.get("value")})
            else:
                accepted.append({**finding,
                                 "accepted": True,
                                 "accept_reason": entry.reason,
                                 "expired": entry.is_expired()})
```
(`_first_hit` stays identity-only — that is what keeps a blocked entry off the stale list.)

- [ ] **Step 4: Run, expect PASS.** Run: `python -m pytest tests/test_accept.py -q`
- [ ] **Step 5: Commit** `fix(accept): expired/ceiling-exceeded entries go active, not suppressed (#2)`.

### Task A3d: End-to-end — ceiling breach reaches the gate as a failure

**Files (repo-B):** add an integration test `tests/test_ceiling_e2e.py`.

- [ ] **Step 1: Failing test** — proves a real wave (normalize → accept → wave_findings.json → gate) fails when a ceilinged metric is breached. Drive the runner's public `partition`+`_apply_accept` path with a synthetic finding list:

```python
import importlib, json
rdw = importlib.import_module("scripts.run_diagnosis_wave")
acc = importlib.import_module("scripts._accept")

def test_ceiling_breach_lands_in_active_and_fails_gate(tmp_path):
    findings = [{"leaf": "complexity", "path": "a.py", "symbol": "f",
                 "metric": "cyclomatic", "value": 40, "threshold": 10}]
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "complexity", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "accepted at 12; CHANGELOG v0.9.0", "max_value": 12}]}
    policy = acc.AcceptPolicy(acc._parse_policy(raw))
    active = rdw._apply_accept(policy, findings, tmp_path)
    assert len(active) == 1  # breach is active, not suppressed
    sidecar = json.loads((tmp_path / "wave_findings.accepted.json").read_text())
    assert sidecar["accepted"] == [] and sidecar["stale"] == []
```

- [ ] **Step 2: Run, expect FAIL** (currently breach would be suppressed). Run: `python -m pytest tests/test_ceiling_e2e.py -q`
- [ ] **Step 3:** No new impl — A3a–A3c already implement it; if FAIL persists, debug per `superpowers:systematic-debugging`. Re-run, expect PASS.
- [ ] **Step 4: Commit** `test(accept): e2e ceiling breach reaches gate active set (#2)`.

## Task A4: Accept-reason quality lint (#3)

**Root cause:** `validate_accept.py` checks only structure. Reasons like "migrated accepted residual — see the repo's frozen ledger" sit green forever, unaudited.

**Design:** A conservative, deterministic reason-quality linter (new gate). A reason passes iff: length ≥ 24 after strip; it is not pure boilerplate (denylist substring match when that phrase is ~the whole reason); and it contains ≥1 *concrete token* (a path-like `*.py`/`a/b`, a rule/metric code `[A-Z]\d{2,}`, an ISO date, or a version tag `v\d+`). Existing boilerplate reasons are mechanically enriched with their finding identity so they pass and become genuinely specific.

**Files (repo-B):**
- Create: `scripts/check_accept_reasons.py`
- Create: `tests/test_check_accept_reasons.py`
- Modify: `.repo-audit/accept.json` (enrich existing reasons — see Step 6)
- Modify: `.github/workflows/check.yml` (wire the gate)

- [ ] **Step 1: Failing tests** — `tests/test_check_accept_reasons.py`:

```python
import importlib
mod = importlib.import_module("scripts.check_accept_reasons")

def test_specific_reason_passes():
    ok, defect = mod.audit_reason(
        "perflint C0206 in scripts/foo.py: dict-iter residual, CHANGELOG v0.9.0")
    assert ok and defect is None

def test_boilerplate_reason_fails():
    ok, defect = mod.audit_reason("migrated accepted residual — see the repo's frozen ledger")
    assert not ok and "boilerplate" in defect.lower()

def test_too_short_reason_fails():
    ok, defect = mod.audit_reason("accepted")
    assert not ok

def test_reason_without_concrete_token_fails():
    ok, defect = mod.audit_reason("this is a perfectly long sentence with no specifics here")
    assert not ok and "concrete" in defect.lower()
```

- [ ] **Step 2: Run, expect FAIL** (module missing). Run: `python -m pytest tests/test_check_accept_reasons.py -q`

- [ ] **Step 3: Implement** `scripts/check_accept_reasons.py`:

```python
#!/usr/bin/env python3
"""Reason-quality gate for `.repo-audit/accept.json` (#3): every accept reason
must be specific and non-boilerplate, not just structurally valid."""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

_acc = importlib.import_module("scripts._accept" if __package__ else "_accept")

MIN_LEN = 24
_BOILERPLATE = (
    "migrated accepted residual",
    "see the repo's frozen ledger",
    "accepted residual",
    "wip", "tbd", "n/a", "todo",
)
_CONCRETE = re.compile(
    r"(\b[\w./-]+\.py\b)"          # a path
    r"|([A-Z]\d{2,})"              # a rule/metric code (C0206, B603)
    r"|(\b\d{4}-\d{2}-\d{2}\b)"    # an ISO date
    r"|(\bv\d+\.\d+)"              # a version tag
)


def audit_reason(reason: str) -> tuple[bool, str | None]:
    text = (reason or "").strip()
    if len(text) < MIN_LEN:
        return False, f"reason too short (<{MIN_LEN} chars): {reason!r}"
    low = text.lower()
    if any(b in low for b in _BOILERPLATE) and not _CONCRETE.search(text):
        return False, f"reason is boilerplate: {reason!r}"
    if not _CONCRETE.search(text):
        return False, f"reason lacks a concrete token (path/code/date/tag): {reason!r}"
    return True, None


def _parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Audit accept.json reason quality.")
    ap.add_argument("--file", type=Path,
                    default=Path(".repo-audit") / "accept.json")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if not args.file.exists():
        print(json.dumps({"status": "pass", "note": "no accept.json"}))
        return 0
    payload = json.loads(args.file.read_text(encoding="utf-8"))
    entries = _acc._parse_policy(payload)  # reuse structural validation
    defects = []
    for i, entry in enumerate(entries):
        ok, defect = audit_reason(entry.reason)
        if not ok:
            defects.append(f"accept[{i}]: {defect}")
    if defects:
        print(json.dumps({"status": "fail", "defects": defects}, indent=2))
        return 1
    print(json.dumps({"status": "pass", "count": len(entries)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run, expect PASS.** Run: `python -m pytest tests/test_check_accept_reasons.py -q`

- [ ] **Step 5: Enrich existing reasons** so the new gate goes green. For each entry in `.repo-audit/accept.json` whose reason fails `audit_reason`, rewrite it deterministically to embed the finding identity + the existing context, e.g.:
  `"<leaf>/<metric> at <path> (<symbol>): residual accepted from v0.8.2 perf-smell rescope; tracked in CHANGELOG"`.
  Run `python scripts/check_accept_reasons.py` and iterate until exit 0. Repeat for repo-P (`perf-benchmark-skill/.repo-audit/accept.json`) and repo-A (`repo-audit-skills/.repo-audit/accept.json` if present) — copy `check_accept_reasons.py` into each and enrich (the script is repo-agnostic).

- [ ] **Step 6: Wire into CI.** In `.github/workflows/check.yml`, add a step in the `convergence-gate` job after the convergence gate step:
```yaml
      - name: Accept-reason quality gate (#3)
        run: python3 scripts/check_accept_reasons.py
```
Add the identical step to repo-P's `check.yml`.

- [ ] **Step 7: Commit** (each repo): `feat(gate): accept-reason quality lint + enrich existing reasons (#3)`.

## Task A5: Toolchain-drift assertion (#10)

**Root cause:** Tool versions live inline in each `check.yml`; nothing asserts the *running* env matches them. This run saw both false reds (missing tools) and false greens (errored lane). Make the pin set a single source of truth and assert it at runtime.

**Files (repo-B; then mirror to repo-P, repo-A):**
- Create: `scripts/toolchain_pins.json`
- Create: `scripts/check_toolchain.py`
- Create: `tests/test_check_toolchain.py`
- Modify: `.github/workflows/check.yml`

- [ ] **Step 1: Create the pin manifest** `scripts/toolchain_pins.json` (mirror the current CI install line; dist names as `importlib.metadata` sees them):
```json
{
  "coverage": "7.14.1",
  "lizard": "1.23.0",
  "radon": "6.0.1",
  "vulture": "2.16",
  "ruff": "0.15.16",
  "mypy": "2.1.0",
  "bandit": "1.9.4",
  "pylint": "3.3.9",
  "astroid": "3.3.11",
  "perflint": "0.8.1",
  "pytest": "9.0.3",
  "hypothesis": "6.155.2"
}
```

- [ ] **Step 2: Failing tests** — `tests/test_check_toolchain.py`:
```python
import importlib
mod = importlib.import_module("scripts.check_toolchain")

def test_match_when_versions_equal():
    drift = mod.diff_versions({"pytest": "9.0.3"}, {"pytest": "9.0.3"})
    assert drift == []

def test_drift_when_version_differs():
    drift = mod.diff_versions({"pytest": "9.0.3"}, {"pytest": "8.0.0"})
    assert drift == ["pytest: pinned 9.0.3, installed 8.0.0"]

def test_drift_when_missing():
    drift = mod.diff_versions({"pytest": "9.0.3"}, {"pytest": None})
    assert drift == ["pytest: pinned 9.0.3, installed MISSING"]
```

- [ ] **Step 3: Run, expect FAIL.** Run: `python -m pytest tests/test_check_toolchain.py -q`

- [ ] **Step 4: Implement** `scripts/check_toolchain.py`:
```python
#!/usr/bin/env python3
"""Toolchain-drift gate (#10): assert installed tool versions match the pin
manifest, so findings are never produced by a drifted/missing toolchain."""
from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path

MANIFEST = Path(__file__).with_name("toolchain_pins.json")


def installed_versions(names) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in names:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def diff_versions(pins: dict[str, str], installed: dict[str, str | None]) -> list[str]:
    drift = []
    for name, want in sorted(pins.items()):
        got = installed.get(name)
        if got is None:
            drift.append(f"{name}: pinned {want}, installed MISSING")
        elif got != want:
            drift.append(f"{name}: pinned {want}, installed {got}")
    return drift


def main() -> int:
    pins = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drift = diff_versions(pins, installed_versions(pins))
    if drift:
        print(json.dumps({"status": "fail", "drift": drift}, indent=2))
        return 1
    print(json.dumps({"status": "pass", "checked": len(pins)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run, expect PASS** (the test uses the pure `diff_versions`; it does not require the tools installed). Run: `python -m pytest tests/test_check_toolchain.py -q`

- [ ] **Step 6: Close the loop in CI.** In `.github/workflows/check.yml` `convergence-gate` job, replace the inline `pip install <pins>` with an install driven by the manifest, then assert:
```yaml
      - name: Install pinned toolchain (from manifest)
        run: |
          python -m pip install --upgrade pip
          python - <<'PY'
          import json, subprocess, sys
          pins = json.load(open("scripts/toolchain_pins.json"))
          pkgs = [f"{n}=={v}" for n, v in pins.items()]
          subprocess.check_call([sys.executable, "-m", "pip", "install", *pkgs])
          PY
      - name: Toolchain-drift gate (#10)
        run: python3 scripts/check_toolchain.py
```
Mirror the manifest + script + CI steps into repo-P and repo-A (repo-A's manifest also lists the leaf tools it installs; adjust names to that repo's CI line).

- [ ] **Step 7: Commit** (each repo): `feat(gate): toolchain pin manifest + drift assertion (#10)`.

## Wave A — Ship

- [ ] All suites green: `python -m pytest tests/ -q` in repo-B and repo-P.
- [ ] **repo-B → v0.9.0:** update `CHANGELOG.md` (entries for #1/#9/#2/#3/#10), bump any version marker, commit, `git tag v0.9.0`, `git push origin wave-a-trustworthy-green && gh pr create` → merge to `main` → `git push origin v0.9.0`.
- [ ] **Re-pin repo-P runner:** in `perf-benchmark-skill/.github/workflows/check.yml` change `git clone --depth 1 --branch v0.8.2 .../repo-audit-refactor-optimize.git /tmp/runner` → `--branch v0.9.0`.
- [ ] **repo-P → v0.5.0:** CHANGELOG + gate fix (#1) + re-pin + #3/#10 mirrors, commit, tag, merge, push tag.
- [ ] **repo-A:** if only the #3/#10 mirrors landed, bump patch or fold into Wave C; otherwise no release in Wave A.
- [ ] **Reinstall:** sync repo-B and repo-P skill trees to `~/.claude/skills/<skill>` and `~/.agents/skills/<skill>`.
- [ ] **Verify:** `gh run list --branch main -L 1` green for all touched repos, incl. convergence + accept-reason + toolchain gates.

---

# WAVE B — Audit the Tooling, Not the Target (#4, #11, #5)

Goal: turn "is the tooling itself correct?" into standing gates via a small **gate-integrity self-audit harness**, so the gap *classes* (errored-lane-passes, lane-not-scoped, assertion-light-tests-pass) cannot recur.

## Task B1: Gate-integrity harness (parametrized invariants) — backbone

**Files (repo-B):** Create `tests/test_gate_integrity.py`. This module *generalizes* the single-instance Wave-A regressions into class-level invariants.

- [ ] **Step 1: Write the invariant tests** (they should pass once Wave A is merged — this task makes the guarantees explicit and parametrized):

```python
"""Gate-integrity self-audit: class-level invariants on the orchestrator itself.
These assert tooling BEHAVIOUR (#4), not target source — the net no leaf can be."""
import importlib, json
import pytest

cwb = importlib.import_module("scripts.check_wave_baseline")
rdw = importlib.import_module("scripts.run_diagnosis_wave")

ALL_LANES = list(json.loads(
    (rdw._DEFAULT_REGISTRY).read_text(encoding="utf-8"))["lanes"])
LANE_NAMES = [l["name"] for l in ALL_LANES]

@pytest.mark.parametrize("errored", LANE_NAMES)
def test_gate_fails_when_any_single_lane_errors(tmp_path, capsys, errored):
    summary = {n: {"exit": 0, "status": "ok", "findings": 0} for n in LANE_NAMES}
    summary[errored] = {"exit": 2, "status": "error", "findings": 0}
    snap = tmp_path / "a.json"; s = tmp_path / "s.json"
    snap.write_text("[]"); s.write_text(json.dumps(summary))
    rc = cwb.main(["--snapshot", str(snap), "--summary", str(s)])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "lane_error"
```

- [ ] **Step 2: Run, expect PASS** (Wave A made this true). Run: `python -m pytest tests/test_gate_integrity.py -q`. If any lane fails the invariant, that is a real fail-open — fix the gate.
- [ ] **Step 3: Commit** `test(gate-integrity): parametrized errored-lane invariant over all lanes (#4)`.

## Task B2: Lane-scoping invariant (#11)

**Root cause:** The perf-smell scoping bug (lane skipped `--source-prefix`, globbed `.venv`) had no general guard — only a perf-smell-specific test. A 10th scopable lane can reintroduce the class.

**Design:** Make the source-scopable set explicit in code AND in the registry, and assert they agree + that every member actually receives `--source-prefix`.

**Files (repo-B):** Modify `scripts/run_diagnosis_wave.py`, `scripts/wave_lanes.json`; create tests in `tests/test_gate_integrity.py`.

- [ ] **Step 1: Failing tests** — add to `tests/test_gate_integrity.py`:
```python
def test_every_source_scoped_lane_receives_source_prefix(tmp_path):
    ctx = rdw._LaneContext(
        repo=tmp_path, out_root=tmp_path, source_prefixes=["scripts"],
        exclude_prefixes=[], rev=None, coverage_json=None,
        security_config=None, hotspot_config=None)
    for lane in rdw.SOURCE_SCOPED_LANES:
        cmd = []
        rdw._append_scope_args(cmd, lane, tmp_path / "leaf.py", ctx)
        assert "--source-prefix" in cmd and "scripts" in cmd, lane

def test_registry_source_scoped_flag_matches_code():
    reg = json.loads(rdw._DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    flagged = {l["name"] for l in reg["lanes"] if l.get("source_scoped")}
    assert flagged == rdw.SOURCE_SCOPED_LANES
```
(`_append_scope_args` calls `_leaf_supports_exclude_prefix`, which runs `leaf --help`; for a nonexistent leaf it returns False and only `--source-prefix` is added — fine for this assertion.)

- [ ] **Step 2: Run, expect FAIL** (`SOURCE_SCOPED_LANES` undefined; registry has no `source_scoped`). Run: `python -m pytest tests/test_gate_integrity.py -k scoped -q`

- [ ] **Step 3: Implement.** In `run_diagnosis_wave.py` add a constant near the top:
```python
# Lanes whose findings are scoped to source via --source-prefix. The registry
# mirrors this via "source_scoped": true; the gate-integrity test asserts parity,
# so adding a 10th scopable lane without scoping it fails CI (#11).
SOURCE_SCOPED_LANES = {"code-health", "security", "dependency", "perf-smell"}
```
Use it in `_append_scope_args`:
```python
    if lane in SOURCE_SCOPED_LANES:
        supports = _leaf_supports_exclude_prefix(leaf)
        cmd.extend(_audit_scope_args(
            context.source_prefixes, context.exclude_prefixes, supports))
```
In `scripts/wave_lanes.json`, add `"source_scoped": true` to the `code-health`, `security`, `dependency`, and `perf-smell` lane entries.

- [ ] **Step 4: Run, expect PASS.** Run: `python -m pytest tests/test_gate_integrity.py -q`
- [ ] **Step 5: Commit** `fix(wave): explicit SOURCE_SCOPED_LANES + registry parity invariant (#11)`.

## Task B3: Per-lane command-construction contract tests (#4)

**Design:** Lock each non-scoped lane's behaviour so a scoping/flag regression is caught at the source-of-truth (command construction), not by luck.

**Files (repo-B):** add to `tests/test_gate_integrity.py`.

- [ ] **Step 1: Failing tests:**
```python
def _ctx(tmp_path, **kw):
    base = dict(repo=tmp_path, out_root=tmp_path, source_prefixes=["scripts"],
                exclude_prefixes=[], rev="HEAD~1", coverage_json=None,
                security_config=None, hotspot_config=None)
    base.update(kw)
    return rdw._LaneContext(**base)

def test_growth_lane_gets_baseline_rev(tmp_path):
    cmd = []; rdw._append_scope_args(cmd, "growth", tmp_path / "leaf.py", _ctx(tmp_path))
    assert cmd[cmd.index("--baseline-rev") + 1] == "HEAD~1"

def test_hotspot_lane_gets_rev(tmp_path):
    cmd = []; rdw._append_scope_args(cmd, "hotspot", tmp_path / "leaf.py", _ctx(tmp_path))
    assert cmd[cmd.index("--rev") + 1] == "HEAD~1"

def test_exec_lane_gets_no_scope_args(tmp_path):
    cmd = []; rdw._append_scope_args(cmd, "exec", tmp_path / "leaf.py", _ctx(tmp_path))
    assert cmd == []
```
- [ ] **Step 2: Run, expect PASS** (these document current correct behaviour; if any fail, that is a latent bug to fix). Run: `python -m pytest tests/test_gate_integrity.py -k "growth or hotspot or exec" -q`
- [ ] **Step 3: Commit** `test(gate-integrity): per-lane command-construction contracts (#4)`.

## Task B4: Test-effectiveness floor on the critical gate modules (#5)

**Root cause:** mutation/TQA/TRT are Tier-2 advisory; an assertion-light, 100%-covered test passes. Graduate a mutation floor for the *directly unit-tested* gate modules (where mutmut can credit tests — unlike repo-A's subprocess-CLI convention block).

**Design:** A new Tier-1 gate runs `test-effectiveness-audit` (mutmut) scoped to a small allowlist of pure modules — exactly the files Wave A hardened — with a kill-rate floor.

**Files (repo-B):**
- Create: `scripts/mutation_targets.json` = `{"modules": ["scripts/_accept.py", "scripts/_wave_findings.py", "scripts/check_wave_baseline.py"], "min_kill_rate": 0.80}`
- Create: `scripts/check_mutation_floor.py` (invokes the `test-effectiveness-audit` leaf at `$LEAF` over the allowlist, parses kill rate, exits 1 below floor; mirror the arg/exit conventions of `scripts/check_coverage_gap.py`).
- Create: `tests/test_check_mutation_floor.py` (unit-test the pure floor-comparison + report-parse logic against a fixture mutmut report; do not run mutmut in the unit test).
- Modify: `.github/workflows/check.yml` (Tier-1 step, `LEAF=/tmp/leaves/skills/test-effectiveness-audit/scripts/test_effectiveness_audit.py`).

- [ ] **Step 1:** Read `scripts/check_coverage_gap.py` to copy its leaf-invocation + `--suite/--source-prefix` + JSON-parse + threshold structure exactly.
- [ ] **Step 2: Failing test** for the pure comparison (e.g. `floor_violations(report, 0.80)` returns the under-floor modules). Run, expect FAIL.
- [ ] **Step 3: Implement** `check_mutation_floor.py` + `mutation_targets.json`. Run unit test, expect PASS.
- [ ] **Step 4: Local smoke** — run the gate for real once against the installed leaf; confirm `_accept.py`/`_wave_findings.py` meet the 0.80 floor. If a module is below floor, add the missing assertion-bearing tests until it passes (this is the #5 payoff). Re-run.
- [ ] **Step 5: Wire CI** Tier-1 step + commit `feat(gate): mutation-kill floor on critical gate modules (#5)`.

## Wave B — Ship

- [ ] Suites green in repo-B (and repo-P if the runner gained `source_scoped`/version surface it consumes).
- [ ] **repo-B → v0.10.0:** CHANGELOG (#4/#11/#5), commit, tag, PR → main, push tag.
- [ ] **Re-pin repo-P runner → v0.10.0** if repo-P relies on the scoping fix; bump repo-P patch, push.
- [ ] Reinstall skill trees to both deploy roots. Verify `gh run list --branch main` green incl. the new mutation-floor + gate-integrity (test job) gates.

---

# WAVE C — Scope / Deploy Parity (#6, #7, #8)

## Task C1: repo-A gates perf-smell, hotspot, exec (#6)

**Root cause:** repo-A's `run_checks.py` gates code-health/security/hygiene/docs/dependency/growth/coverage but **not** perf-smell/hotspot/exec — the same lanes repo-B/repo-P enforce. Same lane, enforced on two repos, unenforced on the third.

**Files (repo-A `repo-audit-skills`):**
- Create: `scripts/check_perf_smell_audit.py`, `scripts/check_hotspot_audit.py`, `scripts/check_exec_audit.py` (mirror `scripts/check_security_audit.py` exactly, via `GateSpec`/`gate_main`).
- Create baselines: `scripts/perf_smell_baseline.json`, `scripts/hotspot_baseline.json`, `scripts/exec_baseline.json` (seed `[]`, then capture the first real snapshot).
- Modify: `scripts/run_checks.py` (register the three in `CHEAP`).
- Create tests under `tests/` mirroring the existing per-gate test pattern.

- [ ] **Step 1: Failing test** — add a registration test asserting the three gate names appear in `run_checks.CHEAP`. Run, expect FAIL.
- [ ] **Step 2: Implement** `check_perf_smell_audit.py` (model on `check_security_audit.py`):
```python
#!/usr/bin/env python3
"""check:perf-smell — ratchet the perf-smell-audit snapshot against the baseline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_common import GateSpec, gate_main, production_prefixes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

def _spec() -> GateSpec:
    out = ROOT / ".self_audit_out" / "perf-smell"
    leaf = ROOT / "skills" / "perf-smell-audit" / "scripts" / "perf_smell_audit.py"
    cmd = [sys.executable, str(leaf), "--root", str(ROOT), "--out-dir", str(out)]
    for prefix in production_prefixes(ROOT):
        cmd += ["--source-prefix", prefix]
    return GateSpec(
        leaf_cmd=cmd,
        findings_file=str(out / "perf_smell_findings.json"),
        snapshot_path=str(ROOT / "scripts" / "perf_smell_snapshot.json"),
        baseline_path="scripts/perf_smell_baseline.json",
        description="Ratchet the perf-smell-audit snapshot against the baseline.")

if __name__ == "__main__":
    sys.exit(gate_main(sys.argv[1:], _spec()))
```
For `check_hotspot_audit.py`: model identically but the hotspot leaf takes `--rev` (mine history) not `--source-prefix` — confirm its findings filename (`hotspot_findings.json`) and add `--rev` per the wave's `_add_hotspot_args` (e.g. an anchor rev). For `check_exec_audit.py`: exec leaf takes no scope args; findings file `exec_findings.json`.
- [ ] **Step 3:** Register in `run_checks.py` `CHEAP`:
```python
    ("perfsmell", "scripts/check_perf_smell_audit.py"),
    ("hotspot", "scripts/check_hotspot_audit.py"),
    ("exec", "scripts/check_exec_audit.py"),
```
- [ ] **Step 4:** Run each new gate locally to seed its baseline, commit the captured baselines. Run `python scripts/run_checks.py`, expect exit 0.
- [ ] **Step 5: Commit** `feat(gate): repo-A gates perf-smell/hotspot/exec for lane parity (#6)`.

## Task C2: Deployed-artifact correctness (#7)

**Root cause:** The duplication leaf hardcodes `Path(__file__).resolve().parents[3] / "node_modules" / ".bin" / "jscpd"`; a standalone-installed leaf has no such ancestor, so the deployed artifact breaks even though in-tree/CI (npm ci) hides it. No dogfood step runs a skill as deployed.

**Files (repo-A):**
- Modify: `skills/duplication-audit/scripts/duplication_audit.py` (robust jscpd resolution).
- Create: `tests/test_standalone_deploy.py` (smoke tests for skills run outside the tree).
- Create: `scripts/check_installer.py` (+ test) — `node --check` the installer + assert its leaf list.

- [ ] **Step 1: Failing test** — `tests/test_standalone_deploy.py`:
```python
import importlib.util, os
from pathlib import Path

LEAF = (Path(__file__).resolve().parents[1]
        / "skills" / "duplication-audit" / "scripts" / "duplication_audit.py")

def _load():
    spec = importlib.util.spec_from_file_location("dup_leaf", LEAF)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def test_jscpd_resolution_honours_env(monkeypatch, tmp_path):
    fake = tmp_path / "jscpd"; fake.write_text("#!/bin/sh\n"); fake.chmod(0o755)
    monkeypatch.setenv("JSCPD_BIN", str(fake))
    mod = _load()
    assert str(mod.resolve_jscpd()) == str(fake)
```

- [ ] **Step 2: Run, expect FAIL** (`resolve_jscpd` missing / env ignored). Run: `python -m pytest tests/test_standalone_deploy.py -q`

- [ ] **Step 3: Implement robust resolution** in `duplication_audit.py` (replace the `parents[3]` assumption):
```python
import os, shutil

def resolve_jscpd() -> Path | None:
    """Resolve the jscpd binary for in-tree AND standalone deployments.
    Order: $JSCPD_BIN -> PATH -> nearest node_modules/.bin ascending -> legacy."""
    env = os.environ.get("JSCPD_BIN")
    if env and Path(env).exists():
        return Path(env)
    on_path = shutil.which("jscpd")
    if on_path:
        return Path(on_path)
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        cand = ancestor / "node_modules" / ".bin" / "jscpd"
        if cand.exists():
            return cand
    return None
```
Use `resolve_jscpd()` where the hardcoded `jscpd_bin` was; when it returns `None`, emit the existing "local jscpd binary not found" diagnostic.

- [ ] **Step 4: Run, expect PASS.** Run: `python -m pytest tests/test_standalone_deploy.py -q`

- [ ] **Step 5: Add a general standalone smoke test** asserting every leaf responds to `--help` when invoked by absolute path from a foreign cwd (catches import/path-assumption breaks at deploy):
```python
import subprocess, sys
SKILLS = (Path(__file__).resolve().parents[1] / "skills")
def test_every_leaf_help_runs_standalone(tmp_path):
    leaves = list(SKILLS.glob("*/scripts/*_audit.py"))
    assert leaves
    for leaf in leaves:
        p = subprocess.run([sys.executable, str(leaf), "--help"],
                           cwd=tmp_path, capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, f"{leaf} failed --help: {p.stderr[-400:]}"
```

- [ ] **Step 6: Installer gate** — `scripts/check_installer.py` runs `node --check bin/install-repo-audit-skills.js` and asserts the expected 19-leaf list is present in the source (regex/parse). Add a test + wire into `run_checks.py` `CHEAP`. **Non-goal (YAGNI):** do not make the installer ship repo-B/repo-P — document in the installer README that the orchestrator/perf repos install separately.
- [ ] **Step 7: Commit** `fix(deploy): robust jscpd resolution + standalone deploy smoke + installer gate (#7)`.

## Task C3: Cross-repo pin-coherence check (#8)

**Root cause:** repo-P pins the runner by tag (`--branch v0.x.y`); nothing verifies that tag actually contains the fix repo-P needs. A stale pin silently runs the old buggy runner and passes.

**Design:** The runner advertises a version + capability set; downstream asserts the pinned runner meets a declared requirement.

**Files (repo-B):**
- Modify: `scripts/run_diagnosis_wave.py` — add `--capabilities` emitting `{"version": __version__, "capabilities": [...]}`; set `__version__ = "0.10.0"` (kept in sync by `check_release.py`).
- Modify: `scripts/check_release.py` — assert `__version__` matches the latest tag (extend its existing release checks).

**Files (repo-P):**
- Create: `scripts/runner_requirements.json` = `{"min_version": "0.9.0", "capabilities": ["lane-error-gate", "metric-ceiling", "lane-timeout"]}`
- Create: `scripts/check_runner_pin.py` (+ test) — invokes `$WAVE_RUNNER --capabilities`, parses, asserts version ≥ min and all required capabilities present; exit 1 otherwise.
- Modify: `.github/workflows/check.yml` — run `check_runner_pin.py` before the convergence gate.

- [ ] **Step 1: Failing test (repo-B)** — `--capabilities` prints the expected JSON. Run, expect FAIL.
- [ ] **Step 2: Implement** in `run_diagnosis_wave.py`:
```python
__version__ = "0.10.0"
CAPABILITIES = ["lane-error-gate", "metric-ceiling", "lane-timeout"]
```
In `_parse_args` add `--capabilities` (store_true); in `main`, handle it before running:
```python
    if getattr(args, "capabilities", False):
        print(json.dumps({"version": __version__, "capabilities": CAPABILITIES}))
        return 0
```
- [ ] **Step 3:** Run repo-B test, expect PASS. Commit.
- [ ] **Step 4: Failing test (repo-P)** — `check_runner_pin.semver_ok("0.10.0", "0.9.0") is True`; missing capability → defect. Run, expect FAIL.
- [ ] **Step 5: Implement** `check_runner_pin.py` (invoke `[sys.executable, os.environ["WAVE_RUNNER"], "--capabilities"]`, parse JSON, compare). Run test, expect PASS.
- [ ] **Step 6: Wire CI** (repo-P) before the convergence gate:
```yaml
      - name: Runner pin-coherence gate (#8)
        env:
          WAVE_RUNNER: /tmp/runner/scripts/run_diagnosis_wave.py
        run: python3 scripts/check_runner_pin.py
```
- [ ] **Step 7: Commit** (both repos): `feat(pin): runner capability surface + downstream pin-coherence gate (#8)`.

## Wave C — Ship

- [ ] **repo-A → v0.8.0:** CHANGELOG (#6/#7), commit, tag, PR → main, push tag.
- [ ] **Re-pin leaf clones to v0.8.0** in repo-B and repo-P `check.yml` (`git clone --branch v0.8.0 .../repo-audit-skills.git /tmp/leaves`).
- [ ] **repo-B → v0.10.0** (already tagged in Wave B if `--capabilities` shipped there; otherwise patch bump for C3 + leaf re-pin), push.
- [ ] **repo-P → v0.6.0:** CHANGELOG (#8) + runner re-pin + leaf re-pin, commit, tag, PR → main, push tag.
- [ ] **Reinstall** all three skill trees to `~/.claude/skills` and `~/.agents/skills`.
- [ ] **Final verify:** `gh run list --branch main -L 1` green for all three repos incl. every new gate (errored-lane, ceiling, accept-reason, toolchain, mutation-floor, repo-A lane parity, installer, pin-coherence).

---

## Self-Review (run by the author before handoff)

**Spec coverage — all 11 gaps mapped to tasks:**
- #1 errored lane passes → A1 (gate reads summary+exit; both repos) + B1 (parametrized invariant).
- #2 accepts mask degradation → A3a–A3d (value carried, `max_value` ceiling, expired/breach→active, e2e).
- #3 accept-reason quality → A4 (linter + enrich + CI).
- #4 audits target not tooling → B1/B3 (gate-integrity + command-construction contracts) + B4 (behaviour verified by mutation floor).
- #5 test effectiveness ungated → B4 (mutation floor on gate modules).
- #6 repo-A lane gaps → C1 (perf-smell/hotspot/exec gates).
- #7 non-Python / deployed artifact → C2 (jscpd resolution, standalone smoke, installer gate).
- #8 pin coherence → C3 (capability surface + pin-coherence gate).
- #9 hang/timeout → A2 (per-lane timeout → error).
- #10 toolchain drift → A5 (pin manifest + drift gate + CI installs from manifest).
- #11 lane-scoping regression class → B2 (SOURCE_SCOPED_LANES + registry parity invariant).

**Class-level invariants present for each fixed class:** errored-lane (B1, all lanes), lane-scoping (B2, registry↔code parity), toolchain (A5, manifest-as-SoT), deploy (C2, every-leaf-standalone smoke), pin (C3, capability assertion).

**Open decisions deliberately settled (YAGNI):** installer does not ship repo-B/repo-P (documented, not coded); mutation floor scoped to 3 pure modules only (repo-A's subprocess-CLI convention block is not in scope — honest no-win per prior C3 pilot); reason-quality linter is conservative (length + boilerplate + one concrete token) to avoid false CI reds.

**Type/name consistency:** `_run_wave()` returns `(out, rc)` in both gate copies; `_lane_errors`, `SOURCE_SCOPED_LANES`, `exceeds_ceiling`, `resolve_jscpd`, `diff_versions`, `audit_reason`, `__version__`/`CAPABILITIES` are referenced with identical names across their tasks and tests.

**Unattended-run readiness:** each wave is independently shippable; every code step has real code; every verify step has an exact command + expected result; ship steps have exact tag/pin/`gh` commands. Waves map cleanly onto goal-preflight branch groups (Wave A → branch group 1, etc.) if driven by the goal orchestrator instead of subagent-driven-development.
