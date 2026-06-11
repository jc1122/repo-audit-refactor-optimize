from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

mod = importlib.import_module("scripts.validate_run_report")


def _write_report_dir(tmp_path: Path, payload: dict, with_md: bool = True) -> Path:
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "run_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    if with_md:
        (report_dir / "run_report.md").write_text("# report", encoding="utf-8")
    return report_dir


def _build_payload(schema_version: int = 2, include_wont_fix: bool = True) -> dict:
    backlog = {"accepted": 1, "deferred": 0, "coverage_gated": 0}
    if schema_version == 2 and include_wont_fix:
        backlog["wont_fix"] = 0
    elif schema_version == 1:
        pass
    return {
        "schema_version": schema_version,
        "repo_root": "/tmp/example",
        "started_utc": "2026-06-11T00:00:00Z",
        "finished_utc": "2026-06-11T00:01:00Z",
        "orchestrator_skill_version": "0.4.0",
        "lanes": {},
        "findings_totals": {},
        "backlog": backlog,
        "batches": [],
        "verification": [],
        "warnings": [],
    }


def test_valid_v2_dir_exits_zero(tmp_path: Path, capsys) -> None:
    run_dir = _write_report_dir(tmp_path, _build_payload(schema_version=2))
    rc = mod.main(["--run-dir", str(run_dir)])
    assert rc == 0
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["status"] == "pass"


def test_missing_top_level_key_exits_one_and_names_key(tmp_path: Path, capsys) -> None:
    payload = _build_payload(schema_version=2)
    payload.pop("finished_utc")
    run_dir = _write_report_dir(tmp_path, payload)
    rc = mod.main(["--run-dir", str(run_dir)])
    assert rc == 1
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["status"] == "fail"
    assert any("finished_utc" in message for message in verdict["defects"])


def test_v2_backlog_missing_wont_fix_exits_one(tmp_path: Path, capsys) -> None:
    run_dir = _write_report_dir(
        tmp_path,
        _build_payload(schema_version=2, include_wont_fix=False),
    )
    rc = mod.main(["--run-dir", str(run_dir)])
    assert rc == 1
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["status"] == "fail"
    assert any("wont_fix" in message for message in verdict["defects"])


def test_schema_1_accepts_v1_backlog_shape(tmp_path: Path, capsys) -> None:
    run_dir = _write_report_dir(tmp_path, _build_payload(schema_version=1))
    rc = mod.main(["--run-dir", str(run_dir), "--schema", "1"])
    assert rc == 0
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["status"] == "pass"


def test_missing_run_report_md_exits_one(tmp_path: Path, capsys) -> None:
    payload = _build_payload(schema_version=2)
    run_dir = _write_report_dir(
        tmp_path,
        payload,
        with_md=False,
    )
    rc = mod.main(["--run-dir", str(run_dir)])
    assert rc == 1
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["status"] == "fail"
