"""Tests for scripts/migrate_baseline_to_accept.py — identity-preserving converter."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

mig = importlib.import_module("scripts.migrate_baseline_to_accept")
acc = importlib.import_module("scripts._accept")

ROWS = [
    {"leaf": "complexity", "path": "scripts/a.py", "symbol": "<module>",
     "metric": "maintainability_index"},
    {"leaf": "hotspot", "path": "SKILL.md", "symbol": "SKILL.md",
     "metric": "churn_complexity_product"},
]


def test_build_policy_preserves_identities():
    payload = mig.build_policy(ROWS, reasons={})
    assert payload["version"] == 1 and len(payload["accept"]) == 2
    ids = {acc.identity_of(e["match"]) for e in payload["accept"]}
    assert ids == {
        ("complexity", "scripts/a.py", "<module>", "maintainability_index"),
        ("hotspot", "SKILL.md", "SKILL.md", "churn_complexity_product"),
    }


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


def test_output_is_schema_valid():
    payload = mig.build_policy(ROWS, reasons={})
    acc._parse_policy(payload)  # raises AcceptError if invalid


def test_main_writes_valid_file(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(ROWS), encoding="utf-8")
    out = tmp_path / "out" / "accept.json"
    rc = mig.main(["--baseline", str(baseline), "--out", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    acc._parse_policy(payload)
    assert len(payload["accept"]) == 2
