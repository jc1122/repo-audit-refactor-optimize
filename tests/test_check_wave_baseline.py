"""Tests for scripts/check_wave_baseline.py — canonical convergence gate."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

mod = importlib.import_module("scripts.check_wave_baseline")


def _dump(path: Path, payload: list[dict]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_status_pass_when_equal(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.json"
    baseline = tmp_path / "baseline.json"
    findings = [
        {"path": "x", "metric": "m", "symbol": "s", "leaf": "a"},
    ]
    _dump(snapshot, findings)
    _dump(baseline, findings)

    rc = mod.main(["--snapshot", str(snapshot), "--baseline", str(baseline)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "pass"
    assert captured["count"] == 1
    assert captured["baseline"] == 1


def test_status_new_findings(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.json"
    baseline = tmp_path / "baseline.json"
    _dump(baseline, [{"path": "x", "metric": "m", "symbol": "s", "leaf": "a"}])
    _dump(
        snapshot,
        [
            {"path": "x", "metric": "m", "symbol": "s", "leaf": "a"},
            {"path": "y", "metric": "m", "symbol": "t", "leaf": "a"},
        ],
    )

    rc = mod.main(["--snapshot", str(snapshot), "--baseline", str(baseline)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["status"] == "fail"
    assert "new_findings" in captured


def test_status_stale_baseline_has_ratchet_message(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.json"
    baseline = tmp_path / "baseline.json"
    _dump(snapshot, [{"path": "x", "metric": "m", "symbol": "s", "leaf": "a"}])
    _dump(
        baseline,
        [
            {"path": "x", "metric": "m", "symbol": "s", "leaf": "a"},
            {"path": "z", "metric": "m", "symbol": "stale", "leaf": "a"},
        ],
    )

    rc = mod.main(["--snapshot", str(snapshot), "--baseline", str(baseline)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["status"] == "fail"
    assert "stale_baseline" in captured
    assert captured["message"] == "ratchet: remove them from wave_baseline.json in the same commit"


def test_finding_identity_is_order_insensitive(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.json"
    baseline = tmp_path / "baseline.json"
    snapshot_payload = {"metric": "m", "symbol": "s", "leaf": "a", "path": "x"}
    baseline_payload = {"path": "x", "leaf": "a", "metric": "m", "symbol": "s"}
    _dump(snapshot, [snapshot_payload])
    _dump(baseline, [baseline_payload])

    rc = mod.main(["--snapshot", str(snapshot), "--baseline", str(baseline)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "pass"
