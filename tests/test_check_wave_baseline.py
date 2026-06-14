"""Tests for scripts/check_wave_baseline.py — canonical convergence gate (Option A).

Convergence trusts the wave's report/accept partition: pass iff the active set
(`wave_findings.json`) is empty AND the accept sidecar's stale list is empty.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

mod = importlib.import_module("scripts.check_wave_baseline")


def _dump(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pass_when_active_empty_and_no_stale(tmp_path, capsys):
    snapshot = tmp_path / "active.json"
    accepted = tmp_path / "accepted.json"
    _dump(snapshot, [])
    _dump(accepted, {"accepted": [{"leaf": "a"}, {"leaf": "b"}], "stale": []})

    rc = mod.main(["--snapshot", str(snapshot), "--accepted", str(accepted)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "pass"
    assert captured["active"] == 0
    assert captured["accepted"] == 2


def test_pass_when_no_accepted_sidecar_given(tmp_path, capsys):
    snapshot = tmp_path / "active.json"
    _dump(snapshot, [])

    rc = mod.main(["--snapshot", str(snapshot)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "pass"
    assert captured["active"] == 0
    assert captured["accepted"] == 0


def test_fail_when_active_non_empty(tmp_path, capsys):
    snapshot = tmp_path / "active.json"
    accepted = tmp_path / "accepted.json"
    _dump(snapshot, [{"path": "y", "metric": "m", "symbol": "t", "leaf": "a"}])
    _dump(accepted, {"accepted": [], "stale": []})

    rc = mod.main(["--snapshot", str(snapshot), "--accepted", str(accepted)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["status"] == "fail"
    assert captured["new_findings"] == [["a", "y", "t", "m"]]


def test_fail_when_stale_non_empty(tmp_path, capsys):
    snapshot = tmp_path / "active.json"
    accepted = tmp_path / "accepted.json"
    _dump(snapshot, [])
    _dump(accepted, {"accepted": [], "stale": ["finding:{'leaf': 'gone'}"]})

    rc = mod.main(["--snapshot", str(snapshot), "--accepted", str(accepted)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["status"] == "fail"
    assert captured["stale_acceptances"] == ["finding:{'leaf': 'gone'}"]


def test_active_wins_over_stale(tmp_path, capsys):
    """A non-empty active set is reported even when stale is also non-empty."""
    snapshot = tmp_path / "active.json"
    accepted = tmp_path / "accepted.json"
    _dump(snapshot, [{"path": "y", "metric": "m", "symbol": "t", "leaf": "a"}])
    _dump(accepted, {"accepted": [], "stale": ["finding:{'leaf': 'gone'}"]})

    rc = mod.main(["--snapshot", str(snapshot), "--accepted", str(accepted)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert "new_findings" in captured
    assert "stale_acceptances" not in captured


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

    out = mod._run_wave()
    assert out == repo / ".wave_out"
    argv = json.loads((repo / ".wave_out" / "argv.json").read_text(encoding="utf-8"))
    assert argv[argv.index("--rev") + 1] == "anchor-sha"
    assert argv[argv.index("--security-config") + 1] == str(security_config)
    assert argv[argv.index("--hotspot-config") + 1] == str(config)
