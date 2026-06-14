# Portable Acceptance Safeguard — Phase 2 Implementation Plan (family-internal migration)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PRECONDITION:** Phase 1 is merged (the `.repo-audit/accept.json` schema + `scripts/_accept.py` exist in repo-B). This plan migrates each family repo's *internal* residual baseline onto that schema **without changing any gate verdict** — every step is count-neutral and proven by running the gate before and after.

**Goal:** Express repo-B, repo-P, and repo-A's internal accepted-residual baselines as `.repo-audit/accept.json` instances (with each frozen-ledger justification carried as `reason`), and point each repo's own convergence gate at the new file — keeping the gate's pass/fail and counts byte-for-byte identical.

**Architecture:** A converter (`scripts/migrate_baseline_to_accept.py`, repo-B) turns a flat `{leaf,path,symbol,metric}` baseline + an optional reasons map into a schema-valid accept file whose `finding`-kind identities are exactly the old baseline's identities. Each repo's gate gains a ~10-line reader that extracts the report-stage `finding` rows from `.repo-audit/accept.json` and feeds them to the **existing** equality-ratchet comparison — so only the baseline's on-disk *format* changes, never the logic. repo-P and repo-A read the shared *format* with their own tiny local readers (no cross-repo code import; consistent with the standalone-vendored-leaf rule).

**Tech Stack:** Python 3.11+ stdlib; pytest (repo-B/P); `npm run check` (repo-A). Each repo migrates in its own commit and proves equivalence in that commit.

**Spec:** `docs/superpowers/specs/2026-06-14-portable-acceptance-safeguard-design.md` (Phase 2 section).

---

## File Structure

- **repo-B** (`~/projects/repo-audit-refactor-optimize`): **create** `scripts/migrate_baseline_to_accept.py` + `tests/test_migrate_baseline.py`; **create** `.repo-audit/accept.json`; **modify** `scripts/check_wave_baseline.py` (read baseline rows from accept.json); **delete** `scripts/wave_baseline.json` (same commit, after equivalence proof). `scripts/wave_frozen.md` stays as the human ledger.
- **repo-P** (`~/projects/perf-benchmark-skill`): **create** `.repo-audit/accept.json`; **modify** `scripts/check_wave_baseline.py` (add a tiny accept reader); **delete** `scripts/wave_baseline.json` (same commit). Run repo-B's converter against repo-P's files (no code copied into repo-P beyond the ~10-line reader).
- **repo-A** (`~/projects/repo-audit-skills`): **create** `.repo-audit/accept.json` (folding `scripts/remediation_excludes.json`); **modify** `scripts/check_self_audit.py` (read baseline rows from accept.json); **delete** `scripts/self_audit_baseline.json` + `scripts/remediation_excludes.json` (same commit). `scripts/self_audit_frozen.md` stays as the human ledger.

**Baseline before starting (record all three):**
- repo-B: `python3 scripts/check_wave_baseline.py --snapshot .wave_out/wave_findings.json --baseline scripts/wave_baseline.json` → record the `{"status":"pass","count":N,"baseline":N}` line.
- repo-P: same command in repo-P.
- repo-A: `npm run check` → record the gate JSON (all green); note the self-audit count.

---

### Task 1 (repo-B): the baseline→accept converter

**Files:**
- Create: `scripts/migrate_baseline_to_accept.py`
- Test: `tests/test_migrate_baseline.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_migrate_baseline.py`:

```python
import importlib
import json
from pathlib import Path

mig = importlib.import_module("scripts.migrate_baseline_to_accept")
acc = importlib.import_module("scripts._accept")

ROWS = [
    {"leaf": "complexity", "path": "scripts/a.py", "symbol": "<module>", "metric": "maintainability_index"},
    {"leaf": "hotspot", "path": "SKILL.md", "symbol": "SKILL.md", "metric": "churn_complexity_product"},
]


def test_build_policy_preserves_identities():
    payload = mig.build_policy(ROWS, reasons={})
    assert payload["version"] == 1 and len(payload["accept"]) == 2
    ids = {acc.identity_of(e["match"]) for e in payload["accept"]}  # helper added below
    assert ids == {("complexity", "scripts/a.py", "<module>", "maintainability_index"),
                   ("hotspot", "SKILL.md", "SKILL.md", "churn_complexity_product")}


def test_each_entry_has_reason_and_report_stage():
    payload = mig.build_policy(ROWS, reasons={})
    for e in payload["accept"]:
        assert e["match"]["kind"] == "finding"
        assert e["reason"]  # non-empty (default pointer or supplied)
        assert e["applies"] == ["report"]


def test_supplied_reason_is_used():
    key = ("complexity", "scripts/a.py", "<module>", "maintainability_index")
    payload = mig.build_policy(ROWS, reasons={key: "single-file tool"})
    match = next(e for e in payload["accept"]
                if e["match"]["path"] == "scripts/a.py")
    assert match["reason"] == "single-file tool"


def test_output_is_schema_valid(tmp_path: Path):
    payload = mig.build_policy(ROWS, reasons={})
    acc._parse_policy(payload)  # raises AcceptError if invalid
```

- [ ] **Step 2: Add the `identity_of` helper to `_accept.py`** (used by the converter test + the gate readers) — append to `scripts/_accept.py`:

```python
def identity_of(match: dict[str, str]) -> tuple[str, str, str, str]:
    """The 4-tuple identity of a `finding`-kind match (parity with _wave_findings.identity)."""
    return (match.get("leaf", ""), match.get("path", ""),
            match.get("symbol", ""), match.get("metric", ""))
```

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m pytest tests/test_migrate_baseline.py -q`
Expected: FAIL — no `scripts.migrate_baseline_to_accept`.

- [ ] **Step 4: Implement the converter** — create `scripts/migrate_baseline_to_accept.py`:

```python
#!/usr/bin/env python3
"""Convert a flat {leaf,path,symbol,metric} baseline into a `.repo-audit/accept.json`.

Identity-preserving and count-neutral: every baseline row becomes a report-stage
`finding` acceptance with the same 4-tuple identity. Reasons default to a pointer at
the frozen ledger and may be overridden per identity.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

_acc = importlib.import_module("scripts._accept" if __package__ else "_accept")

_DEFAULT_REASON = "migrated accepted residual — see the repo's frozen ledger"


def build_policy(
    rows: list[dict[str, str]],
    reasons: dict[tuple[str, str, str, str], str],
) -> dict:
    accept = []
    for r in rows:
        match = {"kind": "finding", "leaf": r.get("leaf", ""), "path": r.get("path", ""),
                 "symbol": r.get("symbol", ""), "metric": r.get("metric", "")}
        ident = _acc.identity_of(match)
        accept.append({"match": match, "reason": reasons.get(ident, _DEFAULT_REASON),
                       "applies": ["report"]})
    return {"version": 1, "accept": accept}


def _parse_args(argv=None):
    ap = argparse.ArgumentParser(description="baseline.json -> .repo-audit/accept.json")
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    rows = json.loads(args.baseline.read_text(encoding="utf-8"))
    payload = build_policy(rows, reasons={})
    _acc._parse_policy(payload)  # fail closed if the result is somehow invalid
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "entries": len(payload["accept"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run to verify it passes**

Run: `python3 -m pytest tests/test_migrate_baseline.py tests/test_accept.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_baseline_to_accept.py scripts/_accept.py tests/test_migrate_baseline.py
git commit -m "feat(accept): identity-preserving baseline->accept converter (Phase 2 tooling)"
```

---

### Task 2 (repo-B): migrate `wave_baseline.json` → `.repo-audit/accept.json`

**Files:**
- Create: `.repo-audit/accept.json`
- Modify: `scripts/check_wave_baseline.py`
- Delete: `scripts/wave_baseline.json`
- Test: `tests/test_check_wave_baseline.py` (append)

- [ ] **Step 1: Generate the accept file**

Run: `python3 scripts/migrate_baseline_to_accept.py --baseline scripts/wave_baseline.json --out .repo-audit/accept.json`
Expected: `{"status": "ok", "entries": 19}` (matches the current baseline count).

- [ ] **Step 2: Verify identity equivalence (manual proof)**

Run:
```bash
python3 - <<'PY'
import json
from scripts import _accept
old = {tuple(sorted(d.items())) for d in json.load(open("scripts/wave_baseline.json"))}
pol = _accept.load_accept(".")
new = {tuple(sorted(e.fields.items())) for e in pol.entries if e.kind == "finding"}
assert old == new, (old ^ new)
print("identities equal:", len(new))
PY
```
Expected: `identities equal: 19` (no symmetric difference).

- [ ] **Step 3: Write the failing test** — append to `tests/test_check_wave_baseline.py`:

```python
def test_baseline_loads_from_accept_when_present(tmp_path, monkeypatch):
    import importlib, json
    cwb = importlib.import_module("scripts.check_wave_baseline")
    repo = tmp_path
    (repo / ".repo-audit").mkdir()
    (repo / ".repo-audit" / "accept.json").write_text(json.dumps({"version": 1, "accept": [
        {"match": {"kind": "finding", "leaf": "c", "path": "p", "symbol": "s", "metric": "m"},
         "reason": "r", "applies": ["report"]}]}), encoding="utf-8")
    rows = cwb._baseline_rows(repo)
    assert rows == [{"leaf": "c", "path": "p", "symbol": "s", "metric": "m"}]
```

- [ ] **Step 2 fails? Run:** `python3 -m pytest tests/test_check_wave_baseline.py -k accept -q` → FAIL (`_baseline_rows` undefined).

- [ ] **Step 4: Repoint the gate** — in `scripts/check_wave_baseline.py`:

Add the `_accept` import next to the `_wf` import (line ~15):

```python
_acc = importlib.import_module("scripts._accept" if __package__ else "_accept")
```

Add the reader and change `ACCEPT` discovery:

```python
ACCEPT = REPO / ".repo-audit" / "accept.json"


def _baseline_rows(repo: Path) -> list[dict]:
    """Report-stage finding identities from .repo-audit/accept.json (the baseline source)."""
    policy = _acc.load_accept(repo)
    return [dict(e.fields) for e in policy.entries
            if e.kind == "finding" and "report" in e.applies]
```

Change `main` so the default baseline comes from the accept file (keep `--baseline` override for tests):

```python
def main(argv=None):
    args = _parse_args(argv)
    current = _load_json(args.snapshot) if args.snapshot else _run_wave()
    baseline = _load_json(args.baseline) if args.baseline else _baseline_rows(REPO)
    return _compare(current, baseline)
```

(`_compare`/`identities`/`_stale_payload` are unchanged — they still operate on `{leaf,path,symbol,metric}` rows, which `_baseline_rows` returns.)

- [ ] **Step 5: Prove the verdict is unchanged, then delete the old file**

Run (still present): `python3 scripts/check_wave_baseline.py --snapshot .wave_out/wave_findings.json`
Expected: `{"status":"pass","count":19,"baseline":19}` — identical to the recorded pre-migration line.

Then:
```bash
git rm scripts/wave_baseline.json
```

- [ ] **Step 6: Run the gate suite + full tests**

Run: `python3 -m pytest tests/test_check_wave_baseline.py tests/ -q`
Expected: PASS. If any existing test references `scripts/wave_baseline.json` by path, update it to construct a temp accept file or pass `--baseline` explicitly (the override path is retained for exactly this).

- [ ] **Step 7: Commit (count-neutral migration)**

```bash
git add .repo-audit/accept.json scripts/check_wave_baseline.py tests/test_check_wave_baseline.py
git commit -m "refactor(accept): repo-B convergence gate reads .repo-audit/accept.json; drop wave_baseline.json (count-neutral, 19==19)"
```

- [ ] **Step 8: Bump + changelog** — `SKILL.md` version bump (e.g. `0.8.0 → 0.8.1`), `CHANGELOG.md` `## 0.8.1` entry noting the internal baseline now lives in `.repo-audit/accept.json`; run `python3 scripts/check_release.py` → pass; commit.

---

### Task 3 (repo-P): migrate `wave_baseline.json` → `.repo-audit/accept.json`

> repo-P (`~/projects/perf-benchmark-skill`) has the same `wave_baseline.json` + `check_wave_baseline.py`
> shape (25 entries). It does NOT import repo-B code; it gets a self-contained ~12-line reader.

**Files (in repo-P):**
- Create: `.repo-audit/accept.json`
- Modify: `scripts/check_wave_baseline.py`
- Delete: `scripts/wave_baseline.json`

- [ ] **Step 1: Generate repo-P's accept file using repo-B's converter** (run from repo-B, write into repo-P):

```bash
python3 ~/projects/repo-audit-refactor-optimize/scripts/migrate_baseline_to_accept.py \
  --baseline ~/projects/perf-benchmark-skill/scripts/wave_baseline.json \
  --out ~/projects/perf-benchmark-skill/.repo-audit/accept.json
```
Expected: `{"status": "ok", "entries": 25}`.

- [ ] **Step 2: Add a self-contained reader to repo-P** — in `~/projects/perf-benchmark-skill/scripts/check_wave_baseline.py`, add a stdlib reader (no import of repo-B); place it near the existing baseline load:

```python
def _baseline_rows():
    """Report-stage finding identities from .repo-audit/accept.json."""
    accept = Path(__file__).resolve().parents[1] / ".repo-audit" / "accept.json"
    if not accept.exists():
        return []
    payload = json.loads(accept.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"invalid accept policy: {accept}")
    rows = []
    for e in payload.get("accept", []):
        m = e.get("match", {})
        if m.get("kind") == "finding" and "report" in e.get("applies", ["report", "remediation"]):
            rows.append({k: m.get(k, "") for k in ("leaf", "path", "symbol", "metric")})
    return rows
```

Then route the gate's baseline through it (mirror repo-P's existing `main`/`_compare` — replace the `wave_baseline.json` load with `_baseline_rows()` when no explicit `--baseline` is given). Keep the `--baseline` test override.

- [ ] **Step 3: Prove equivalence + delete the old file**

Run (repo-P): `python3 scripts/check_wave_baseline.py --snapshot .wave_out/wave_findings.json`
Expected: `{"status":"pass","count":25,"baseline":25}` — identical to the recorded pre-migration line. Then `git rm scripts/wave_baseline.json`.

- [ ] **Step 4: Gate + commit (repo-P)**

Run: `python3 -m pytest tests/ -q` → PASS; `python3 scripts/check_release.py` (or repo-P's release gate) → pass.
```bash
cd ~/projects/perf-benchmark-skill
git add .repo-audit/accept.json scripts/check_wave_baseline.py
git rm scripts/wave_baseline.json
git commit -m "refactor(accept): repo-P gate reads .repo-audit/accept.json; drop wave_baseline.json (25==25)"
```
Then bump repo-P version + CHANGELOG (e.g. `0.4.0 → 0.4.1`) and commit.

---

### Task 4 (repo-A): migrate `self_audit_baseline.json` (+ fold `remediation_excludes.json`)

> repo-A (`~/projects/repo-audit-skills`) baseline is 40 rows of `{leaf,metric,path,symbol}` (the
> `symbol` carries a content-hash for duplication rows — preserved verbatim). Its gate is
> `check_self_audit.py` → `gate_common.verdict(current, baseline, baseline_path)`. Same identity-
> preserving migration, plus `remediation_excludes.json` becomes `path` + `applies:["remediation"]`
> entries colocated in the same file (repo-A's own report-stage gate ignores remediation entries).

**Files (in repo-A):**
- Create: `.repo-audit/accept.json`
- Modify: `scripts/check_self_audit.py`
- Delete: `scripts/self_audit_baseline.json`, `scripts/remediation_excludes.json`

- [ ] **Step 1: Generate repo-A's finding entries** (run repo-B's converter against repo-A's baseline):

```bash
python3 ~/projects/repo-audit-refactor-optimize/scripts/migrate_baseline_to_accept.py \
  --baseline ~/projects/repo-audit-skills/scripts/self_audit_baseline.json \
  --out ~/projects/repo-audit-skills/.repo-audit/accept.json
```
Expected: `{"status": "ok", "entries": 40}`.

- [ ] **Step 2: Fold `remediation_excludes.json` into the same file** — append the remediation entries. Add a `path` entry per `exclude_paths` glob from `scripts/remediation_excludes.json` (its `dead_code.exclude_paths` = `["**/tests/fixtures/**"]`, reason from its `reason`), with `"applies": ["remediation"]`. The resulting file has 40 `finding` (report) entries + 1 `path` (remediation) entry. Validate:

```bash
python3 ~/projects/repo-audit-refactor-optimize/scripts/validate_accept.py \
  --file ~/projects/repo-audit-skills/.repo-audit/accept.json
```
Expected: `{"status": "pass"}`.

- [ ] **Step 3: Add a self-contained reader to repo-A** — in `~/projects/repo-audit-skills/scripts/check_self_audit.py`, add the same stdlib `_baseline_rows()` reader as repo-P (Task 3 Step 2), returning only the `finding`/report rows in repo-A's identity shape `{leaf,metric,path,symbol}`. Route `main`'s `baseline = json.loads(... self_audit_baseline.json ...)` (line ~57) through `_baseline_rows()` when no `--baseline` override is given.

- [ ] **Step 4: Prove count-neutral, then delete the old files**

Run (repo-A): `npm run check` — Expected: every gate green, including `check:selfaudit` with the **same** self-audit count as the recorded pre-migration baseline (40 accepted; 0 new; 0 stale). Confirm by grepping the emitted gate JSON (never a piped exit code — lesson L4). Then:

```bash
cd ~/projects/repo-audit-skills
git rm scripts/self_audit_baseline.json scripts/remediation_excludes.json
```

- [ ] **Step 5: Update references to the deleted files** — `grep -rn "self_audit_baseline.json\|remediation_excludes.json" scripts/ tests/ docs/ README.md AGENTS.md`. Repoint any tooling/doc reference to `.repo-audit/accept.json` (e.g. `check_self_audit.py`'s `BASELINE_PATH`, any test fixture path, the SP15 candidate note). The orchestrator-side consumer of `remediation_excludes.json` (repo-B's `mprr_run._engine_accept_policy`, Phase 1) already auto-discovers `.repo-audit/accept.json` first and only falls back to the old file — so removing it is safe.

- [ ] **Step 6: Full gate + commit (repo-A)**

Run: `npm run check` → all gates green (grep the JSON). Run `npm run check:release` (or `python3 scripts/check_release.py`) → pass.
```bash
git add .repo-audit/accept.json scripts/check_self_audit.py
git rm scripts/self_audit_baseline.json scripts/remediation_excludes.json
git commit -m "refactor(accept): repo-A selfaudit gate reads .repo-audit/accept.json; fold remediation_excludes; drop legacy baselines (40==40, count-neutral)"
```
Then bump repo-A family version + CHANGELOG (e.g. `0.7.0 → 0.7.1`) per its release process and commit.

---

## Final verification (all three repos)

- [ ] **repo-B:** `python3 -m pytest tests/ -q` pass; `python3 scripts/check_wave_baseline.py --snapshot .wave_out/wave_findings.json` → `pass count==baseline` matching the pre-migration count; `scripts/wave_baseline.json` gone; `.repo-audit/accept.json` present + `validate_accept.py` pass.
- [ ] **repo-P:** gate pass with identical count; `wave_baseline.json` gone; accept file valid.
- [ ] **repo-A:** `npm run check` all green (grepped JSON), self-audit count unchanged; `self_audit_baseline.json` + `remediation_excludes.json` gone; accept file valid (40 finding + 1 remediation path entry).
- [ ] Each repo's `*_frozen.md` ledger is retained (human justification) and now cross-references `.repo-audit/accept.json` as the machine source.
- [ ] No repo imports another repo's code: repo-P and repo-A use their own ~12-line readers of the shared *format*.
- [ ] Do NOT push/tag/merge — integration + reinstall is the separate human-gated step, per repo.

---

## Self-Review (completed by planner)

- **Spec coverage (Phase 2 section):** converter → Task 1; repo-B/repo-P (`wave_baseline.json` + `wave_frozen.md`, gate via shared `identity`) → Tasks 2-3; repo-A (`self_audit_baseline.json` + `self_audit_frozen.md`, fold `remediation_excludes.json`) → Task 4; count-neutral equivalence proof in every migration → Steps "prove … then delete"; cross-repo no-import (local readers) → Tasks 3-4. All Phase-2 requirements mapped.
- **Count-neutrality is the safety net:** every migration changes only the baseline's on-disk format; the gate's `_compare`/`verdict` equality logic is untouched, and each task runs the gate before (recorded) and after (must match) in the same commit. A mismatch = stop, not proceed.
- **Placeholder scan:** no TBD/TODO; converter + reader code is complete; repo-P/repo-A readers are shown in full (Task 3 Step 2) and reused by reference in Task 4 Step 3 with the identity-shape difference called out.
- **Type/identity consistency:** `build_policy(rows, reasons) -> {version,accept}`, `identity_of(match)`, `_baseline_rows(repo)->list[{leaf,path,symbol,metric}]` are defined once and used consistently; repo-A's reader returns its `{leaf,metric,path,symbol}` shape (same four keys, gate-compatible). The `finding`-kind entry shape matches Phase 1's `_accept._parse_entry` (validated via `validate_accept.py` in Task 4 Step 2).
- **Ordering/preconditions:** Phase 1 must be merged (provides `_accept.py`, `validate_accept.py`, the Phase-1 engine fallback that makes `remediation_excludes.json` removal safe). Repos migrate independently and in any order after Task 1.
- **Out of scope (intentional):** no change to gate *semantics* (equality ratchet preserved), no migration of the per-lane gates that have empty baselines (coverage/security/dependency/etc. in repo-A — all currently 0 entries, nothing to migrate), no deletion of the human `*_frozen.md` ledgers.
```