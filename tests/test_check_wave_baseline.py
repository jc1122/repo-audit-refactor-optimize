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


def test_run_wave_forwards_anchor_and_wave_configs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = tmp_path / "runner.py"
    runner.write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "out = Path(sys.argv[sys.argv.index('--out-dir') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'wave_findings.json').write_text('[]', encoding='utf-8')\n"
        "(out / 'argv.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    anchor = tmp_path / "wave_anchor.txt"
    anchor.write_text("anchor-sha\n", encoding="utf-8")
    config = tmp_path / "hotspot_audit_config.json"
    config.write_text("{}\n", encoding="utf-8")
    security_config = tmp_path / "security_audit_config.json"
    security_config.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(mod, "REPO", repo)
    monkeypatch.setattr(mod, "WAVE_ANCHOR", anchor)
    monkeypatch.setattr(mod, "SECURITY_CONFIG", security_config)
    monkeypatch.setattr(mod, "HOTSPOT_CONFIG", config)
    monkeypatch.setenv("WAVE_RUNNER", str(runner))
    monkeypatch.setenv("SKILLS_ROOT", str(tmp_path / "skills"))
    monkeypatch.delenv("WAVE_REV", raising=False)
    monkeypatch.delenv("SECURITY_CONFIG", raising=False)
    monkeypatch.delenv("HOTSPOT_CONFIG", raising=False)

    assert mod._run_wave() == []
    argv = json.loads((repo / ".wave_out" / "argv.json").read_text(encoding="utf-8"))
    assert argv[argv.index("--rev") + 1] == "anchor-sha"
    assert argv[argv.index("--security-config") + 1] == str(security_config)
    assert argv[argv.index("--hotspot-config") + 1] == str(config)
