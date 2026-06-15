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
        "(out / 'wave_summary.json').write_text('{}', encoding='utf-8')\n"
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

    out, rc = mod._run_wave()
    assert out == repo / ".wave_out"
    assert rc == 0
    argv = json.loads((repo / ".wave_out" / "argv.json").read_text(encoding="utf-8"))
    assert argv[argv.index("--rev") + 1] == "anchor-sha"
    assert argv[argv.index("--security-config") + 1] == str(security_config)
    assert argv[argv.index("--hotspot-config") + 1] == str(config)


def _wave_runner(path: Path) -> None:
    """A fake runner that records its argv + writes a passing wave output."""
    path.write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "out = Path(sys.argv[sys.argv.index('--out-dir') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'wave_findings.json').write_text('[]', encoding='utf-8')\n"
        "(out / 'wave_summary.json').write_text('{}', encoding='utf-8')\n"
        "(out / 'argv.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )


def test_run_wave_builds_the_full_command_contract(tmp_path, monkeypatch):
    """Lock every cmd flag/value _run_wave constructs (#5 mutation contract)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = tmp_path / "runner.py"
    _wave_runner(runner)
    skills = tmp_path / "skills"

    monkeypatch.setattr(mod, "REPO", repo)
    monkeypatch.setattr(mod, "WAVE_ANCHOR", tmp_path / "absent_anchor.txt")
    monkeypatch.setattr(mod, "SECURITY_CONFIG", tmp_path / "absent_sec.json")
    monkeypatch.setattr(mod, "HOTSPOT_CONFIG", tmp_path / "absent_hot.json")
    monkeypatch.setenv("WAVE_RUNNER", str(runner))
    monkeypatch.setenv("SKILLS_ROOT", str(skills))
    monkeypatch.delenv("WAVE_REV", raising=False)
    monkeypatch.delenv("SECURITY_CONFIG", raising=False)
    monkeypatch.delenv("HOTSPOT_CONFIG", raising=False)

    out, rc = mod._run_wave()
    assert rc == 0
    argv = json.loads((repo / ".wave_out" / "argv.json").read_text(encoding="utf-8"))
    # --repo / --out-dir carry the real REPO and .wave_out paths
    assert argv[argv.index("--repo") + 1] == str(repo)
    assert argv[argv.index("--out-dir") + 1] == str(repo / ".wave_out")
    # --skills-root comes from SKILLS_ROOT
    assert argv[argv.index("--skills-root") + 1] == str(skills)
    # --source-prefix is fixed to "scripts"
    assert argv[argv.index("--source-prefix") + 1] == "scripts"
    # no anchor/configs present -> those flags are absent
    assert "--rev" not in argv
    assert "--security-config" not in argv
    assert "--hotspot-config" not in argv


def test_run_wave_defaults_runner_when_env_unset(tmp_path, monkeypatch):
    """Unset WAVE_RUNNER -> the DEFAULT_RUNNER path is used (kills dropped-default)."""
    captured = {}

    def fake_run(cmd, check):
        captured["cmd"] = cmd
        out = Path(cmd[cmd.index("--out-dir") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "wave_findings.json").write_text("[]", encoding="utf-8")

        class _P:
            returncode = 0

        return _P()

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(mod, "REPO", repo)
    monkeypatch.setattr(mod, "WAVE_ANCHOR", tmp_path / "absent.txt")
    monkeypatch.setattr(mod, "SECURITY_CONFIG", tmp_path / "absent_s.json")
    monkeypatch.setattr(mod, "HOTSPOT_CONFIG", tmp_path / "absent_h.json")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.delenv("WAVE_RUNNER", raising=False)
    monkeypatch.delenv("WAVE_REV", raising=False)

    out, rc = mod._run_wave()
    assert rc == 0
    # the runner argument is the module's DEFAULT_RUNNER, not None
    assert captured["cmd"][1] == mod.DEFAULT_RUNNER
    assert captured["cmd"][0] == sys.executable


def test_load_json_reads_payload(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"k": [1, 2, 3]}), encoding="utf-8")
    assert mod._load_json(p) == {"k": [1, 2, 3]}


def test_converge_lane_error_payload_carries_named_keys(tmp_path, capsys):
    """The lane-error verdict must use exactly the documented output keys (#5)."""
    rc = mod._converge([], {"stale": []}, ["security"], 1)
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["reason"] == "lane_error"
    assert captured["errored_lanes"] == ["security"]
    assert captured["runner_exit"] == 1


def test_converge_fails_on_nonzero_runner_exit_even_without_lane_errors(capsys):
    rc = mod._converge([], {"stale": []}, [], 2)
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["reason"] == "lane_error"
    assert captured["runner_exit"] == 2


def test_converge_pass_payload_counts_accepted(capsys):
    rc = mod._converge([], {"accepted": [{"a": 1}, {"b": 2}], "stale": []}, [], 0)
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "pass"
    assert captured["accepted"] == 2
    assert captured["active"] == 0


def test_lane_errors_only_flags_error_status():
    summary = {
        "a": {"status": "error"},
        "b": {"status": "ok"},
        "c": {"status": "error"},
        "d": "not-a-dict",
    }
    assert mod._lane_errors(summary) == ["a", "c"]


def test_converge_tolerates_sidecar_missing_stale_key(capsys):
    """A sidecar without a 'stale' key must default to [] (not None)."""
    rc = mod._converge([], {"accepted": []}, [], 0)
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["status"] == "pass"


def test_converge_reports_stale_acceptances(capsys):
    rc = mod._converge([], {"accepted": [], "stale": ["finding:{'leaf': 'gone'}"]}, [], 0)
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["stale_acceptances"] == ["finding:{'leaf': 'gone'}"]


def test_run_wave_forwards_env_rev_and_configs(tmp_path, monkeypatch):
    """Env-supplied rev/security/hotspot config must reach the command (#5)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = tmp_path / "runner.py"
    _wave_runner(runner)

    monkeypatch.setattr(mod, "REPO", repo)
    monkeypatch.setattr(mod, "WAVE_ANCHOR", tmp_path / "absent.txt")
    monkeypatch.setattr(mod, "SECURITY_CONFIG", tmp_path / "absent_s.json")
    monkeypatch.setattr(mod, "HOTSPOT_CONFIG", tmp_path / "absent_h.json")
    monkeypatch.setenv("WAVE_RUNNER", str(runner))
    monkeypatch.setenv("WAVE_REV", "deadbeef")
    monkeypatch.setenv("SECURITY_CONFIG", "/sec.json")
    monkeypatch.setenv("HOTSPOT_CONFIG", "/hot.json")
    monkeypatch.setenv("SKILLS_ROOT", str(tmp_path / "skills"))

    out, rc = mod._run_wave()
    assert rc == 0
    argv = json.loads((repo / ".wave_out" / "argv.json").read_text(encoding="utf-8"))
    assert argv[argv.index("--rev") + 1] == "deadbeef"
    assert argv[argv.index("--security-config") + 1] == "/sec.json"
    assert argv[argv.index("--hotspot-config") + 1] == "/hot.json"


def test_run_wave_reads_anchor_when_env_rev_absent(tmp_path, monkeypatch):
    """No WAVE_REV but an anchor file present -> --rev comes from the anchor."""
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = tmp_path / "runner.py"
    _wave_runner(runner)
    anchor = tmp_path / "anchor.txt"
    anchor.write_text("anchor-rev\n", encoding="utf-8")

    monkeypatch.setattr(mod, "REPO", repo)
    monkeypatch.setattr(mod, "WAVE_ANCHOR", anchor)
    monkeypatch.setattr(mod, "SECURITY_CONFIG", tmp_path / "absent_s.json")
    monkeypatch.setattr(mod, "HOTSPOT_CONFIG", tmp_path / "absent_h.json")
    monkeypatch.setenv("WAVE_RUNNER", str(runner))
    monkeypatch.setenv("SKILLS_ROOT", str(tmp_path / "skills"))
    monkeypatch.delenv("WAVE_REV", raising=False)
    monkeypatch.delenv("SECURITY_CONFIG", raising=False)
    monkeypatch.delenv("HOTSPOT_CONFIG", raising=False)

    out, rc = mod._run_wave()
    argv = json.loads((repo / ".wave_out" / "argv.json").read_text(encoding="utf-8"))
    assert argv[argv.index("--rev") + 1] == "anchor-rev"


def test_run_wave_propagates_runner_returncode(tmp_path, monkeypatch):
    """check=False is required: a nonzero runner exit is returned, not raised (#5)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def fake_run(cmd, check):
        # check must be False; if a mutant flips it to True this fake would
        # still return, but the real subprocess.run(check=True) on a nonzero
        # exit raises -> the assertion on returncode below pins the contract.
        out = Path(cmd[cmd.index("--out-dir") + 1])
        out.mkdir(parents=True, exist_ok=True)

        class _P:
            returncode = 7

        return _P()

    monkeypatch.setattr(mod, "REPO", repo)
    monkeypatch.setattr(mod, "WAVE_ANCHOR", tmp_path / "absent.txt")
    monkeypatch.setattr(mod, "SECURITY_CONFIG", tmp_path / "absent_s.json")
    monkeypatch.setattr(mod, "HOTSPOT_CONFIG", tmp_path / "absent_h.json")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setenv("WAVE_RUNNER", "/runner.py")
    monkeypatch.delenv("WAVE_REV", raising=False)

    out, rc = mod._run_wave()
    assert rc == 7


def test_main_live_branch_reads_wave_output_files(tmp_path, monkeypatch, capsys):
    """The non-snapshot main() path reads the three wave_*.json files (#5)."""
    out_dir = tmp_path / ".wave_out"
    out_dir.mkdir()
    reads: list[str] = []

    def fake_run_wave():
        return out_dir, 0

    def fake_load_json(path):
        reads.append(Path(path).name)
        if Path(path).name == "wave_findings.json":
            return []
        if Path(path).name == "wave_findings.accepted.json":
            return {"accepted": [], "stale": []}
        return {}  # wave_summary.json

    monkeypatch.setattr(mod, "_run_wave", fake_run_wave)
    monkeypatch.setattr(mod, "_load_json", fake_load_json)

    rc = mod.main([])  # no --snapshot -> live branch
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0 and captured["status"] == "pass"
    # exact filenames are part of the contract (kills case/operator mutants)
    assert reads == [
        "wave_findings.json",
        "wave_findings.accepted.json",
        "wave_summary.json",
    ]


def test_main_live_branch_fails_on_runner_error(tmp_path, monkeypatch, capsys):
    out_dir = tmp_path / ".wave_out"
    out_dir.mkdir()

    monkeypatch.setattr(mod, "_run_wave", lambda: (out_dir, 3))
    monkeypatch.setattr(
        mod, "_load_json",
        lambda path: [] if "findings" in str(path) and "accepted" not in str(path)
        else {"accepted": [], "stale": []} if "accepted" in str(path) else {},
    )

    rc = mod.main([])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert captured["reason"] == "lane_error"
    assert captured["runner_exit"] == 3


def test_main_snapshot_default_sidecar_when_no_accepted(tmp_path, capsys):
    """--snapshot without --accepted defaults the sidecar to {'stale': []}."""
    snap = tmp_path / "a.json"
    _dump(snap, [])
    rc = mod.main(["--snapshot", str(snap)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0 and captured["status"] == "pass"
