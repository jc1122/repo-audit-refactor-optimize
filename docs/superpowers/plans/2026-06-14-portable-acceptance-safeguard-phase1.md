# Portable Acceptance Safeguard — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single portable, auto-discovered `<repo>/.repo-audit/accept.json` that the diagnosis wave and the MPRR engine honor, so any audited repo can mark a finding acceptable (by exact identity, path glob, or rule class) once and have it neither re-flagged nor auto-fixed — recorded with a reason, never silently dropped.

**Architecture:** One new stdlib module `scripts/_accept.py` owns the schema, fail-closed validation, and a 3-granularity matcher; a JSON schema file is the format's source of truth; a `validate_accept.py` CLI mirrors `validate_run_report.py`. The wave (`run_diagnosis_wave.py`) and the engine (`mprr_run.py`) load the policy for their target repo and partition findings through it. The existing `--baseline` flat array is adapted into `finding`-kind acceptances (back-compat). Entirely in the repo-B project; no leaf or perf-engine change.

**Tech Stack:** Python 3.11+ stdlib (`json`, `pathlib`, `fnmatch`, `datetime`, `dataclasses`); pytest. Gates: `python3 -m pytest tests/ -q` + `python3 scripts/check_release.py`.

**Spec:** `docs/superpowers/specs/2026-06-14-portable-acceptance-safeguard-design.md`

---

## File Structure

- **Create** `schema/accept.schema.json` — the format's single source of truth (informational + used by `validate_accept.py` for the human-readable error catalog; validation is hand-rolled stdlib, no jsonschema dependency).
- **Create** `scripts/_accept.py` — loader + fail-closed validator + 3-kind matcher + `partition`. Public surface: `AcceptError`, `AcceptEntry`, `AcceptPolicy`, `load_accept(repo, extra=None)`, `from_baseline(rows)`.
- **Create** `scripts/validate_accept.py` — fail-closed CLI validator (JSON verdict, exit 0/1).
- **Modify** `scripts/run_diagnosis_wave.py` — auto-discover the in-repo file; add `--accept`; route suppression through `_accept`; write `wave_findings.accepted.json` (keep `wave_findings.suppressed.json` for back-compat).
- **Modify** `scripts/mprr_run.py` — in `_cmd_plan`, filter findings through `_accept` (remediation stage) before normalize; honor `remediation_excludes.json` as a fallback; write `mprr_excluded.json`.
- **Create** `references/acceptance.md`; **Modify** `SKILL.md` (one cross-link + version), `references/pipeline.md`, `CHANGELOG.md`.
- **Tests:** **Create** `tests/test_accept.py`, `tests/test_validate_accept.py`; **extend** `tests/test_run_diagnosis_wave.py`, `tests/test_mprr_run.py` (verify it exists first — see Task 5).

**Baseline before starting:** `git rev-parse HEAD`; `python3 -m pytest tests/ -q` (record the pass count, expected 256); `python3 scripts/check_release.py` → `{"status": "pass"}`. Tasks are ordered: model+validation → matcher → CLI validator → wave wiring → engine wiring → reference doc → docs/version. Each task ends green.

---

### Task 1: `_accept.py` — data model + fail-closed loading/validation

**Files:**
- Create: `schema/accept.schema.json`
- Create: `scripts/_accept.py`
- Test: `tests/test_accept.py`

- [ ] **Step 1: Write the schema file** — create `schema/accept.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "repo-audit acceptance policy",
  "type": "object",
  "required": ["version", "accept"],
  "properties": {
    "version": {"const": 1},
    "accept": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["match", "reason"],
        "properties": {
          "match": {
            "type": "object",
            "required": ["kind"],
            "properties": {
              "kind": {"enum": ["finding", "path", "rule"]},
              "leaf": {"type": "string"},
              "path": {"type": "string"},
              "symbol": {"type": "string"},
              "metric": {"type": "string"},
              "glob": {"type": "string"}
            }
          },
          "reason": {"type": "string", "minLength": 1},
          "applies": {
            "type": "array",
            "items": {"enum": ["report", "remediation"]}
          },
          "expires": {"type": ["string", "null"]}
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test** — create `tests/test_accept.py`:

```python
import importlib
import json
from pathlib import Path

import pytest

acc = importlib.import_module("scripts._accept")


def _write(repo: Path, payload: object) -> Path:
    d = repo / ".repo-audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "accept.json").write_text(json.dumps(payload), encoding="utf-8")
    return repo


def test_missing_file_is_empty_policy(tmp_path: Path):
    policy = acc.load_accept(tmp_path)
    assert policy.entries == []


def test_loads_valid_policy(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "intentional"},
    ]})
    policy = acc.load_accept(tmp_path)
    assert len(policy.entries) == 1
    e = policy.entries[0]
    assert e.kind == "path" and e.reason == "intentional"
    assert e.applies == frozenset({"report", "remediation"})  # default both


def test_malformed_json_raises(tmp_path: Path):
    d = tmp_path / ".repo-audit"; d.mkdir()
    (d / "accept.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_missing_reason_raises(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [{"match": {"kind": "path", "glob": "x"}}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_unknown_kind_raises(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "nope"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_bad_applies_value_raises(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "x"}, "reason": "r", "applies": ["typo"]}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_path_traversal_glob_rejected(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "../escape/**"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_finding_kind_requires_four_fields(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "finding", "leaf": "c", "path": "p"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_rule_kind_requires_leaf_or_metric(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "rule"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)
```

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m pytest tests/test_accept.py -q`
Expected: collection error / FAIL — `scripts._accept` has no `load_accept`/`AcceptError`.

- [ ] **Step 4: Implement the model + loader** — create `scripts/_accept.py`:

```python
"""Portable acceptance policy: load + fail-closed validate `<repo>/.repo-audit/accept.json`.

The audit leaves detect everything by design; this module is consulted one layer up
(the wave's reporting stage and the MPRR engine's remediation stage) to mark findings
acceptable. A malformed policy is a hard error — never silently "accept nothing" or
"accept everything". See docs/superpowers/specs/2026-06-14-portable-acceptance-safeguard-design.md.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ACCEPT_RELPATH = Path(".repo-audit") / "accept.json"
_STAGES = frozenset({"report", "remediation"})
_KINDS = frozenset({"finding", "path", "rule"})


class AcceptError(ValueError):
    """Raised on any malformed acceptance policy (fail-closed)."""


@dataclass(frozen=True)
class AcceptEntry:
    kind: str
    fields: dict[str, str]
    reason: str
    applies: frozenset[str]
    expires: str | None

    def is_expired(self, today: date | None = None) -> bool:
        """True only for an ISO date in the past; non-date tokens never auto-expire."""
        if not self.expires:
            return False
        try:
            parsed = date.fromisoformat(self.expires)
        except ValueError:
            return False
        return parsed < (today or date.today())


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AcceptError(msg)


def _parse_entry(raw: Any, index: int) -> AcceptEntry:
    _require(isinstance(raw, dict), f"accept[{index}] must be an object")
    match = raw.get("match")
    _require(isinstance(match, dict), f"accept[{index}].match must be an object")
    kind = match.get("kind")
    _require(kind in _KINDS, f"accept[{index}].match.kind must be one of {sorted(_KINDS)}")
    reason = raw.get("reason")
    _require(isinstance(reason, str) and reason.strip(), f"accept[{index}].reason is required")

    applies_raw = raw.get("applies", ["report", "remediation"])
    _require(isinstance(applies_raw, list) and applies_raw, f"accept[{index}].applies must be a non-empty array")
    _require(all(a in _STAGES for a in applies_raw),
             f"accept[{index}].applies values must be in {sorted(_STAGES)}")

    fields: dict[str, str] = {}
    for key in ("leaf", "path", "symbol", "metric", "glob"):
        if key in match:
            _require(isinstance(match[key], str), f"accept[{index}].match.{key} must be a string")
            fields[key] = match[key]

    if kind == "finding":
        missing = [k for k in ("leaf", "path", "symbol", "metric") if k not in fields]
        _require(not missing, f"accept[{index}] finding match missing {missing}")
    elif kind == "path":
        _require("glob" in fields, f"accept[{index}] path match needs 'glob'")
        _require(".." not in fields["glob"] and not fields["glob"].startswith("/"),
                 f"accept[{index}] glob must be repo-relative (no '..' or leading '/')")
    else:  # rule
        _require("leaf" in fields or "metric" in fields,
                 f"accept[{index}] rule match needs 'leaf' and/or 'metric'")

    expires = raw.get("expires")
    _require(expires is None or isinstance(expires, str), f"accept[{index}].expires must be string|null")
    return AcceptEntry(kind, fields, reason, frozenset(applies_raw), expires)


def _parse_policy(payload: Any) -> list[AcceptEntry]:
    _require(isinstance(payload, dict), "accept policy must be a JSON object")
    _require(payload.get("version") == 1, "accept policy version must be 1")
    accept = payload.get("accept")
    _require(isinstance(accept, list), "accept policy 'accept' must be an array")
    return [_parse_entry(raw, i) for i, raw in enumerate(accept)]
```

- [ ] **Step 5: Add `AcceptPolicy` + `load_accept` + `from_baseline`** — append to `scripts/_accept.py`:

```python
class AcceptPolicy:
    """A validated set of acceptance entries with stage-scoped matching."""

    def __init__(self, entries: list[AcceptEntry]) -> None:
        self.entries = entries

    def merge(self, other: "AcceptPolicy") -> "AcceptPolicy":
        return AcceptPolicy(self.entries + other.entries)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AcceptError(f"{path} is invalid JSON: {exc}") from exc
    except OSError as exc:
        raise AcceptError(f"cannot read {path}: {exc}") from exc


def load_accept(repo: Path, extra: Path | None = None) -> AcceptPolicy:
    """Discover `<repo>/.repo-audit/accept.json` (+ optional --accept file), validated."""
    entries: list[AcceptEntry] = []
    in_repo = Path(repo) / ACCEPT_RELPATH
    if in_repo.exists():
        entries.extend(_parse_policy(_read_json(in_repo)))
    if extra is not None:
        entries.extend(_parse_policy(_read_json(Path(extra))))
    return AcceptPolicy(entries)


def from_baseline(rows: list[dict[str, str]]) -> AcceptPolicy:
    """Adapt a legacy flat --baseline array into report-stage finding acceptances."""
    entries = [
        AcceptEntry(
            "finding",
            {k: str(r.get(k, "")) for k in ("leaf", "path", "symbol", "metric")},
            "(legacy --baseline)",
            frozenset({"report"}),
            None,
        )
        for r in rows
    ]
    return AcceptPolicy(entries)
```

- [ ] **Step 6: Run to verify it passes**

Run: `python3 -m pytest tests/test_accept.py -q`
Expected: PASS (9 tests).

- [ ] **Step 7: Commit**

```bash
git add schema/accept.schema.json scripts/_accept.py tests/test_accept.py
git commit -m "feat(accept): portable acceptance policy model + fail-closed loader (Phase 1)"
```

---

### Task 2: `_accept.py` — 3-kind matcher + `partition`

**Files:**
- Modify: `scripts/_accept.py` (add `matches`/`partition` to `AcceptPolicy`)
- Test: `tests/test_accept.py` (append)

- [ ] **Step 1: Write the failing test** — append to `tests/test_accept.py`:

```python
def _policy(entries):
    return acc.AcceptPolicy([acc._parse_entry(e, i) for i, e in enumerate(entries)])


WAVE_FINDING = {"leaf": "complexity", "path": "scripts/a.py",
                "symbol": "<module>", "metric": "maintainability_index"}


def test_finding_kind_exact_match():
    p = _policy([{"match": {"kind": "finding", **WAVE_FINDING}, "reason": "r"}])
    assert p.matches(WAVE_FINDING, "report") is not None
    other = {**WAVE_FINDING, "path": "scripts/b.py"}
    assert p.matches(other, "report") is None


def test_path_kind_matches_path_attr():
    p = _policy([{"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "r"}])
    assert p.matches({"path": "skills/x/tests/fixtures/dirty.py"}, "report") is not None
    assert p.matches({"path": "scripts/a.py"}, "report") is None


def test_path_kind_matches_files_list_for_engine():
    p = _policy([{"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "r"}])
    finding = {"files": ["src/x.py", "tests/fixtures/y.py"]}
    assert p.matches(finding, "remediation") is not None


def test_rule_kind_leaf_and_metric_subset():
    p = _policy([{"match": {"kind": "rule", "leaf": "hotspot",
                            "metric": "churn_complexity_product"}, "reason": "r"}])
    assert p.matches({"leaf": "hotspot", "path": "CHANGELOG.md", "symbol": "x",
                      "metric": "churn_complexity_product"}, "report") is not None
    assert p.matches({"leaf": "hotspot", "metric": "other"}, "report") is None


def test_applies_scopes_the_stage():
    p = _policy([{"match": {"kind": "path", "glob": "x.py"}, "reason": "r",
                  "applies": ["remediation"]}])
    assert p.matches({"path": "x.py"}, "remediation") is not None
    assert p.matches({"path": "x.py"}, "report") is None


def test_partition_splits_and_reports_stale():
    p = _policy([
        {"match": {"kind": "finding", **WAVE_FINDING}, "reason": "accepted"},
        {"match": {"kind": "path", "glob": "never/**"}, "reason": "dead"},
    ])
    other = {**WAVE_FINDING, "path": "scripts/b.py"}
    active, accepted, stale = p.partition([WAVE_FINDING, other], "report")
    assert [f["path"] for f in active] == ["scripts/b.py"]
    assert accepted[0]["accepted"] is True and accepted[0]["accept_reason"] == "accepted"
    assert any("never/**" in s for s in stale)


def test_partition_marks_expired():
    p = _policy([{"match": {"kind": "path", "glob": "x.py"}, "reason": "r",
                  "expires": "2000-01-01"}])
    active, accepted, stale = p.partition([{"path": "x.py"}], "report")
    assert active == [] and accepted[0]["expired"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_accept.py -k "match or partition or rule or applies or expired" -q`
Expected: FAIL — `AcceptPolicy` has no `matches`/`partition`.

- [ ] **Step 3: Implement the matcher** — add these methods inside `class AcceptPolicy` in `scripts/_accept.py` (after `merge`):

```python
    @staticmethod
    def _entry_matches(entry: AcceptEntry, finding: dict[str, Any]) -> bool:
        f = entry.fields
        if entry.kind == "finding":
            return all(str(finding.get(k, "")) == f[k]
                       for k in ("leaf", "path", "symbol", "metric"))
        if entry.kind == "path":
            glob = f["glob"]
            paths = [finding.get("path", "")] + list(finding.get("files", []) or [])
            return any(p and fnmatch.fnmatch(p, glob) for p in paths)
        # rule: every specified key must equal (AND), at least one is present
        return all(str(finding.get(k, "")) == v for k, v in f.items())

    def matches(self, finding: dict[str, Any], stage: str) -> AcceptEntry | None:
        for entry in self.entries:
            if stage in entry.applies and self._entry_matches(entry, finding):
                return entry
        return None

    def partition(
        self, findings: list[dict[str, Any]], stage: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """→ (active, accepted, stale). Accepted carry reason + expired flag; stale =
        stage-scoped entries that matched nothing (described for the sidecar)."""
        stage_entries = [e for e in self.entries if stage in e.applies]
        matched: set[int] = set()
        active: list[dict[str, Any]] = []
        accepted: list[dict[str, Any]] = []
        for finding in findings:
            hit = None
            for i, entry in enumerate(stage_entries):
                if self._entry_matches(entry, finding):
                    hit = (i, entry)
                    break
            if hit is None:
                active.append(finding)
            else:
                i, entry = hit
                matched.add(i)
                accepted.append({**finding, "accepted": True,
                                 "accept_reason": entry.reason,
                                 "expired": entry.is_expired()})
        stale = [f"{e.kind}:{e.fields}" for i, e in enumerate(stage_entries)
                 if i not in matched]
        return active, accepted, stale
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_accept.py -q`
Expected: PASS (16 tests total).

- [ ] **Step 5: Commit**

```bash
git add scripts/_accept.py tests/test_accept.py
git commit -m "feat(accept): 3-kind matcher (finding/path/rule) + stage partition"
```

---

### Task 3: `validate_accept.py` — fail-closed CLI validator

**Files:**
- Create: `scripts/validate_accept.py`
- Test: `tests/test_validate_accept.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_validate_accept.py`:

```python
import importlib
import json
from pathlib import Path

va = importlib.import_module("scripts.validate_accept")


def _write(tmp: Path, payload) -> Path:
    p = tmp / "accept.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_valid_file_exits_zero(tmp_path, capsys):
    f = _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "x"}, "reason": "r"}]})
    rc = va.main(["--file", str(f)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "pass"


def test_invalid_file_exits_one_with_defect(tmp_path, capsys):
    f = _write(tmp_path, {"version": 1, "accept": [{"match": {"kind": "path"}, "reason": "r"}]})
    rc = va.main(["--file", str(f)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["status"] == "fail" and out["defects"]


def test_missing_file_exits_one(tmp_path, capsys):
    rc = va.main(["--file", str(tmp_path / "nope.json")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["status"] == "fail"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_validate_accept.py -q`
Expected: FAIL — no `scripts.validate_accept`.

- [ ] **Step 3: Implement** — create `scripts/validate_accept.py`:

```python
#!/usr/bin/env python3
"""Fail-closed validator for a `.repo-audit/accept.json` file."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

_acc = importlib.import_module("scripts._accept" if __package__ else "_accept")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an accept.json file.")
    parser.add_argument("--file", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.file.exists():
        print(json.dumps({"status": "fail", "defects": [f"Missing file: {args.file}"]}))
        return 1
    try:
        _acc._parse_policy(json.loads(args.file.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "fail", "defects": [f"invalid JSON: {exc}"]}))
        return 1
    except _acc.AcceptError as exc:
        print(json.dumps({"status": "fail", "defects": [str(exc)]}))
        return 1
    print(json.dumps({"status": "pass"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest tests/test_validate_accept.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_accept.py tests/test_validate_accept.py
git commit -m "feat(accept): fail-closed validate_accept.py CLI"
```

---

### Task 4: wire the acceptance policy into the diagnosis wave

**Files:**
- Modify: `scripts/run_diagnosis_wave.py` (`_parse_args`, `main`)
- Test: `tests/test_run_diagnosis_wave.py` (append)

> **Audit note:** `main` today (lines ~424-435) suppresses only when `--baseline` is passed, via
> `_wave_findings.partition`, writing `wave_findings.suppressed.json`. This task makes the wave
> ALSO auto-discover `<repo>/.repo-audit/accept.json`, merge any `--baseline` (as `finding` entries)
> and `--accept`, partition through `_accept`, and additionally write `wave_findings.accepted.json`.
> The legacy `wave_findings.suppressed.json` keeps being written (same `suppressed`/`stale_baseline`
> shape) so any existing reader is unaffected.

- [ ] **Step 1: Write the failing test** — append to `tests/test_run_diagnosis_wave.py`:

```python
import importlib
import json
from pathlib import Path

wave = importlib.import_module("scripts.run_diagnosis_wave")


def test_resolve_accept_auto_discovers_repo_file(tmp_path: Path):
    (tmp_path / ".repo-audit").mkdir()
    (tmp_path / ".repo-audit" / "accept.json").write_text(json.dumps(
        {"version": 1, "accept": [
            {"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "r"}]}),
        encoding="utf-8")
    policy = wave._resolve_accept(tmp_path, accept=None, baseline=None)
    assert len(policy.entries) == 1


def test_resolve_accept_merges_baseline_rows(tmp_path: Path):
    base = tmp_path / "b.json"
    base.write_text(json.dumps([
        {"leaf": "c", "path": "p", "symbol": "<module>", "metric": "mi"}]), encoding="utf-8")
    policy = wave._resolve_accept(tmp_path, accept=None, baseline=base)
    assert policy.entries[0].kind == "finding"
    assert policy.entries[0].applies == frozenset({"report"})


def test_apply_accept_writes_accepted_sidecar(tmp_path: Path):
    findings = [{"leaf": "c", "path": "scripts/a.py", "symbol": "<module>", "metric": "mi"},
                {"leaf": "c", "path": "scripts/b.py", "symbol": "f", "metric": "x"}]
    acc = importlib.import_module("scripts._accept")
    policy = acc.AcceptPolicy([acc._parse_entry(
        {"match": {"kind": "finding", "leaf": "c", "path": "scripts/a.py",
                   "symbol": "<module>", "metric": "mi"}, "reason": "ok"}, 0)])
    active = wave._apply_accept(policy, findings, tmp_path)
    assert [f["path"] for f in active] == ["scripts/b.py"]
    sidecar = json.loads((tmp_path / "wave_findings.accepted.json").read_text())
    assert sidecar["accepted"][0]["accept_reason"] == "ok"
    assert (tmp_path / "wave_findings.suppressed.json").exists()  # back-compat
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_run_diagnosis_wave.py -k "resolve_accept or apply_accept" -q`
Expected: FAIL — `_resolve_accept`/`_apply_accept` undefined.

- [ ] **Step 3: Add the `--accept` arg** — in `scripts/run_diagnosis_wave.py` `_parse_args`, after the `--baseline` argument (line ~96), add:

```python
    parser.add_argument(
        "--accept", type=Path,
        help="Extra acceptance policy file merged with <repo>/.repo-audit/accept.json",
    )
```

- [ ] **Step 4: Import `_accept` and add the two helpers** — at the top of `scripts/run_diagnosis_wave.py`, alongside the existing `_wave_findings` import, add the import the same import-robust way (match the file's existing style — verify whether it uses `import importlib` or a direct `from scripts import _wave_findings`; mirror it):

```python
_accept = importlib.import_module("scripts._accept" if __package__ else "_accept")
```

Then add these helpers near `_write_wave_outputs`:

```python
def _resolve_accept(
    repo: Path, accept: Path | None, baseline: Path | None
) -> "_accept.AcceptPolicy":
    """Auto-discover the in-repo policy, merge --accept and a legacy --baseline."""
    policy = _accept.load_accept(repo, accept)  # raises AcceptError on a bad file
    if baseline is not None:
        rows = _wave_findings.load_baseline(baseline)  # raises on bad input
        policy = policy.merge(_accept.from_baseline(rows))
    return policy


def _apply_accept(
    policy: "_accept.AcceptPolicy", findings: list[dict[str, str]], out_dir: Path
) -> list[dict[str, str]]:
    """Partition at the report stage; write the accepted + back-compat sidecars."""
    active, accepted, stale = policy.partition(findings, "report")
    (out_dir / "wave_findings.accepted.json").write_text(
        json.dumps({"accepted": accepted, "stale": stale}, indent=2), encoding="utf-8")
    # back-compat: keep the old suppressed.json shape for existing readers
    (out_dir / "wave_findings.suppressed.json").write_text(
        json.dumps({"suppressed": accepted, "stale_baseline": stale}, indent=2),
        encoding="utf-8")
    return active
```

- [ ] **Step 5: Replace the suppression block in `main`** — in `scripts/run_diagnosis_wave.py`, replace the current `if args.baseline is not None:` block (lines ~424-435) with:

```python
    policy = _resolve_accept(args.repo, args.accept, args.baseline)
    if policy.entries:
        wave_findings = _apply_accept(policy, wave_findings, args.out_dir)
    return _write_wave_outputs(args.out_dir, wave_exit, summary, wave_findings, timings)
```

- [ ] **Step 6: Run the wave + accept suites**

Run: `python3 -m pytest tests/test_run_diagnosis_wave.py tests/test_accept.py -q`
Expected: PASS. The existing `--baseline` behavior is preserved (same suppressed.json shape); if an existing test asserts suppression happens only with `--baseline`, it still holds because an absent in-repo file + no flags yields an empty policy (no sidecars written).

- [ ] **Step 7: Commit**

```bash
git add scripts/run_diagnosis_wave.py tests/test_run_diagnosis_wave.py
git commit -m "feat(wave): auto-discover .repo-audit/accept.json + --accept; route suppression via _accept (G-report)"
```

---

### Task 5: wire the acceptance policy into the MPRR engine (remediation stage)

**Files:**
- Modify: `scripts/mprr_run.py` (`_cmd_plan`)
- Test: `tests/test_mprr_run.py` (**verify it exists first; create if absent**)

> **Audit note:** `_cmd_plan` (line ~52) builds items via `_items(a.findings, a.triage)` →
> `mprr_normalize.normalize(_load(a.findings))`. The hook is to filter the raw findings list at the
> remediation stage *before* normalize, using the policy loaded from `a.repo`. `remediation_excludes.json`
> (a `{dead_code: {exclude_paths: [...]}}` shape in repo-A) is honored as a fallback by mapping each
> `exclude_paths` glob to a `path` + `applies:["remediation"]` entry.

- [ ] **Step 1: Confirm the test file** — run `ls tests/test_mprr_run.py`. If it exists, APPEND; if not, CREATE it with the imports below. (Either way, do not clobber existing tests.)

- [ ] **Step 2: Write the failing test** — add to `tests/test_mprr_run.py`:

```python
import importlib
import json
from pathlib import Path

run = importlib.import_module("scripts.mprr_run")


def test_remediation_excludes_fallback_maps_to_path_entries(tmp_path: Path):
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "remediation_excludes.json").write_text(json.dumps(
        {"dead_code": {"exclude_paths": ["**/fixtures/**"], "reason": "intentional"}}),
        encoding="utf-8")
    policy = run._engine_accept_policy(tmp_path)
    finding = {"files": ["tests/fixtures/x.py"]}
    assert policy.matches(finding, "remediation") is not None


def test_filter_findings_drops_remediation_accepted_and_writes_sidecar(tmp_path: Path):
    (tmp_path / ".repo-audit").mkdir()
    (tmp_path / ".repo-audit" / "accept.json").write_text(json.dumps(
        {"version": 1, "accept": [
            {"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "intentional"}]}),
        encoding="utf-8")
    findings = [{"id": "a", "files": ["src/x.py"]},
                {"id": "b", "files": ["tests/fixtures/y.py"]}]
    kept = run._filter_remediation(findings, tmp_path, run_dir=tmp_path)
    assert [f["id"] for f in kept] == ["a"]
    excluded = json.loads((tmp_path / "mprr_excluded.json").read_text())
    assert excluded["excluded"][0]["id"] == "b"
    assert excluded["excluded"][0]["accept_reason"] == "intentional"
```

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m pytest tests/test_mprr_run.py -q`
Expected: FAIL — `_engine_accept_policy`/`_filter_remediation` undefined.

- [ ] **Step 4: Implement** — in `scripts/mprr_run.py`, add the `_accept` import next to the existing imports (line ~16):

```python
from scripts import _accept  # noqa: E402
```

Then add the two helpers above `_cmd_plan`:

```python
def _engine_accept_policy(repo: Path) -> "_accept.AcceptPolicy":
    """Policy for the target repo + back-compat remediation_excludes.json fallback."""
    policy = _accept.load_accept(repo)
    legacy = Path(repo) / "scripts" / "remediation_excludes.json"
    if legacy.exists():
        data = json.loads(legacy.read_text())
        entries = []
        for section in data.values():
            if not isinstance(section, dict):
                continue
            reason = section.get("reason", "(remediation_excludes.json)")
            for glob in section.get("exclude_paths", []):
                entries.append(_accept.AcceptEntry(
                    "path", {"glob": glob}, reason,
                    frozenset({"remediation"}), None))
        policy = policy.merge(_accept.AcceptPolicy(entries))
    return policy


def _filter_remediation(
    findings: list[dict[str, Any]], repo: Path, run_dir: Path
) -> list[dict[str, Any]]:
    """Drop findings accepted at the remediation stage; record them in a sidecar."""
    policy = _engine_accept_policy(repo)
    if not policy.entries:
        return findings
    active, excluded, stale = policy.partition(findings, "remediation")
    (Path(run_dir) / "mprr_excluded.json").write_text(
        json.dumps({"excluded": excluded, "stale": stale}, indent=2), encoding="utf-8")
    return active
```

- [ ] **Step 5: Apply the filter in `_cmd_plan`** — in `scripts/mprr_run.py` `_cmd_plan`, replace the `items = _items(a.findings, a.triage)` line (~54) with a pre-filter of the findings file. Since `_items` reads the file by path, add an overload that accepts already-loaded findings; the minimal change:

```python
def _cmd_plan(a: argparse.Namespace) -> int:
    run_dir = Path(a.run_dir)
    raw_findings = _load(a.findings)
    if a.repo:
        raw_findings = _filter_remediation(raw_findings, Path(a.repo), run_dir)
    items = mprr_normalize.normalize(raw_findings)
    items += mprr_normalize.from_triage_report(_load(a.triage))
    items = sorted(items, key=lambda it: it.id)
    by_id = {it.id: it for it in items}
    state = _read_state(run_dir)
```

(The remainder of `_cmd_plan` from `running: dict[...]` onward is unchanged.)

- [ ] **Step 6: Run to verify it passes**

Run: `python3 -m pytest tests/test_mprr_run.py tests/ -k "mprr" -q`
Expected: PASS. Existing MPRR plan tests pass an empty/absent `--repo` or a tmp repo with no policy → `_filter_remediation` returns the findings unchanged (no behavior change).

- [ ] **Step 7: Commit**

```bash
git add scripts/mprr_run.py tests/test_mprr_run.py
git commit -m "feat(mprr): honor .repo-audit/accept.json (remediation stage) + remediation_excludes fallback (G-fix)"
```

---

### Task 6: authoring reference (`references/acceptance.md`)

**Files:**
- Create: `references/acceptance.md`
- Modify: `SKILL.md` (add one cross-link line under the diagnosis/remediation sections)

- [ ] **Step 1: Write the reference** — create `references/acceptance.md`:

```markdown
# Acceptance policy — `.repo-audit/accept.json`

Drop this file in an audited repo's root to mark findings acceptable. The audit **leaves
still detect everything**; acceptance is applied at the wave (reporting) and the MPRR
engine (remediation). Accepted findings are recorded with their reason in a sidecar —
never silently dropped. A malformed file is a hard error.

## Schema (version 1)

`{"version": 1, "accept": [ <entry>, ... ]}`. Each entry:

- `match.kind` — `finding` | `path` | `rule`
  - `finding`: requires `leaf`, `path`, `symbol`, `metric` (exact identity).
  - `path`: requires `glob` (repo-relative; no `..` or leading `/`). Matches a finding's
    `path` or any of its `files`.
  - `rule`: requires `leaf` and/or `metric` (subset; both → AND).
- `reason` — required, non-empty.
- `applies` — subset of `["report","remediation"]`; default both. `report` = not flagged
  by the wave/gate; `remediation` = never auto-fixed by the MPRR engine.
- `expires` — optional ISO date (`YYYY-MM-DD`) or version token. A past ISO date still
  applies but is flagged `expired` for re-triage; non-date tokens are informational.

## Example

(See the three-entry example in the design spec.)

## Validate

`python3 scripts/validate_accept.py --file <repo>/.repo-audit/accept.json` → `{"status":"pass"}` or
a `fail` verdict with defects. Auto-discovered by `run_diagnosis_wave.py` (also `--accept <file>`)
and by `mprr_run.py plan --repo <repo>`; `--baseline` rows are honored as report-stage `finding`
entries. `scripts/remediation_excludes.json` is honored as a back-compat remediation fallback.
```

- [ ] **Step 2: Cross-link from SKILL.md** — in `SKILL.md`, add one line under Stage 2 (Diagnosis) and the MPRR section: "Accepted-residuals policy: drop `.repo-audit/accept.json` in the target repo to suppress (report) and/or exclude-from-fix (remediation) findings — see `references/acceptance.md`."

- [ ] **Step 3: Commit**

```bash
git add references/acceptance.md SKILL.md
git commit -m "docs(accept): authoring reference + SKILL.md cross-link"
```

---

### Task 7: docs + CHANGELOG + version bump + final verification

**Files:**
- Modify: `references/pipeline.md`, `CHANGELOG.md`, `SKILL.md` (version frontmatter)

- [ ] **Step 1: Document in pipeline.md** — in `references/pipeline.md`, add a short subsection under the diagnosis-wave / MPRR sections describing auto-discovery of `.repo-audit/accept.json`, the `report`/`remediation` stages, the `wave_findings.accepted.json` and `mprr_excluded.json` sidecars, and the fail-closed contract.

- [ ] **Step 2: Bump version** — in `SKILL.md` frontmatter, change `version: 0.7.7` → `version: 0.8.0`.

- [ ] **Step 3: CHANGELOG** — add a `## 0.8.0` entry at the top (heading text exactly `## 0.8.0` so `check_release.py` matches it):

```markdown
## 0.8.0

feat(accept): portable acceptance safeguard. A new `<repo>/.repo-audit/accept.json`
(schema in `schema/accept.schema.json`, validator `scripts/validate_accept.py`) marks findings
acceptable at three granularities (exact finding / path glob / rule class), blocking reporting
and/or remediation (`applies`), with a mandatory reason and optional expiry. Auto-discovered by
the diagnosis wave (also `--accept`; legacy `--baseline` rows fold in as report-stage findings,
new `wave_findings.accepted.json` sidecar) and the MPRR engine (remediation stage, with the old
`remediation_excludes.json` honored as a fallback, new `mprr_excluded.json` sidecar). Malformed
policies fail closed. Leaves still detect everything; acceptance is applied at the wave/engine
layer and every accepted finding is recorded with its reason. Family-internal baselines migrate
onto this schema in Phase 2.
```

- [ ] **Step 4: Final gates**

Run: `python3 -m pytest tests/ -q` — Expected: PASS (256 baseline + the new tests from Tasks 1-5).
Run: `python3 scripts/check_release.py` — Expected: `{"status": "pass"}` (version ↔ CHANGELOG heading in sync).

- [ ] **Step 5: Commit**

```bash
git add references/pipeline.md CHANGELOG.md SKILL.md
git commit -m "docs(accept): document acceptance policy; bump repo-B 0.7.7 -> 0.8.0"
```

---

## Final verification

- [ ] `python3 -m pytest tests/ -q` → all pass (baseline + Tasks 1-5 tests).
- [ ] `python3 scripts/check_release.py` → `{"status": "pass"}`.
- [ ] End-to-end smoke: create `/tmp/acc/.repo-audit/accept.json` with one `path` entry, run a scoped wave on `/tmp/acc`, confirm matching findings land in `wave_findings.accepted.json` (with reason) and not in `wave_findings.json`; corrupt the file and confirm the wave exits non-zero with a clear `AcceptError`.
- [ ] `python3 scripts/validate_accept.py --file <a valid file>` → `{"status":"pass"}`; on a `reason`-less entry → `fail` with a defect.
- [ ] Working tree clean, 7 task commits present.
- [ ] Do NOT push/tag/merge — integration is a separate human-gated step (re-install the skill after merge so `~/.agents/skills` picks up the change).

---

## Self-Review (completed by planner)

- **Spec coverage:** schema → Task 1; fail-closed validation → Task 1 + Task 3; 3-kind matcher + `applies` + expiry + counted sidecar → Task 2; wave auto-discovery + `--accept` + `--baseline` back-compat → Task 4; engine remediation exclusion + `remediation_excludes` fallback → Task 5; reference doc → Task 6; pipeline docs + version → Task 7. Every Phase-1 spec component maps to a task.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; the one prose deferral ("see the three-entry example in the design spec") is a doc cross-reference, not an implementation gap.
- **Type/identity consistency:** `AcceptError`, `AcceptEntry(kind, fields, reason, applies, expires)`, `AcceptPolicy.{merge,matches,partition,_entry_matches}`, `load_accept(repo, extra)`, `from_baseline(rows)`, `_parse_entry(raw, index)`, `_parse_policy(payload)` are defined in Tasks 1-2 and used consistently in Tasks 3-5 and the tests. `partition(findings, stage) -> (active, accepted, stale)` matches every call site. The wave `finding` shape `{leaf,path,symbol,metric}` matches `_wave_findings._normalize_finding`. The engine finding shape uses `files` (matching `mprr_normalize._files_for`).
- **Existing-test impact:** the wave change preserves `--baseline` behavior (same `suppressed.json` shape) and adds `accepted.json`; with no in-repo file and no flags the policy is empty so no sidecar is written and no current test flips. The MPRR change is a no-op when `--repo` is empty/has no policy. `validate_run_report.py` is untouched (mirrored only as a style template).
- **Import robustness:** `_accept.py` is imported the same import-robust way the file already imports `_wave_findings`/its siblings (Task 4 Step 4, Task 5 Step 4); verify the host file's existing convention and match it rather than assuming `importlib`.
- **Out of scope (intentional):** no family-internal baseline migration (Phase 2), no leaf/perf-engine change, no jsonschema dependency (hand-rolled stdlib validation).
