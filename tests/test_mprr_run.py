"""Tests for scripts/mprr_run.py — orchestrator-facing CLI over persisted state."""
from __future__ import annotations
import importlib, json, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
run = importlib.import_module("scripts.mprr_run")


def _findings(tmp):
    data = [
        {"id": "d1", "leaf": "dead-code", "signal": "DELETE", "path": "a.py",
         "evidence": {"raw": ""}, "confidence": "high"},
        {"id": "d2", "leaf": "dead-code", "signal": "DELETE", "path": "b.py",
         "evidence": {"raw": ""}, "confidence": "high"},
    ]
    p = tmp / "f.json"; p.write_text(json.dumps(data)); return p


def test_plan_emits_disjoint_packets_and_persists_state(tmp_path):
    run_dir = tmp_path / "rd"; run_dir.mkdir()
    code = run.main(["plan", "--run-dir", str(run_dir),
                     "--findings", str(_findings(tmp_path)), "--ceiling", "4"])
    assert code == 0
    state = json.loads((run_dir / "mprr_state.json").read_text())
    assert set(state["running"]) == {"d1", "d2"}            # disjoint -> both start
    assert set(state["locked"]) == {"a.py", "b.py"}


def test_plan_creates_run_dir_when_absent(tmp_path):
    # Regression: plan must own (mkdir) its --run-dir. It previously crashed with
    # FileNotFoundError writing mprr_excluded.json / mprr_state.json into a
    # not-yet-existing dir when called standalone (orchestrated flow masked it).
    (tmp_path / ".repo-audit").mkdir()
    (tmp_path / ".repo-audit" / "accept.json").write_text(json.dumps(
        {"version": 1, "accept": [
            {"match": {"kind": "path", "glob": "**/fixtures/**"},
             "reason": "intentional"}]}), encoding="utf-8")
    run_dir = tmp_path / "does" / "not" / "exist"  # absent + nested (parents=True)
    code = run.main(["plan", "--run-dir", str(run_dir),
                     "--findings", str(_findings(tmp_path)),
                     "--repo", str(tmp_path), "--ceiling", "4"])
    assert code == 0
    assert (run_dir / "mprr_state.json").is_file()
    assert (run_dir / "mprr_excluded.json").is_file()


def test_reaudit_counts_residual_items(tmp_path):
    code = run.main(["reaudit", "--findings", str(_findings(tmp_path))])
    assert code == 2  # exit code carries the residual count (0 == converged)


def test_integrate_releases_locks_on_gate_fail(tmp_path):
    run_dir = tmp_path / "rd"; run_dir.mkdir()
    run.main(["plan", "--run-dir", str(run_dir),
              "--findings", str(_findings(tmp_path)), "--ceiling", "4"])
    ev = tmp_path / "e.json"; ev.write_text(json.dumps({"tests_passed": False}))
    code = run.main(["integrate", "--run-dir", str(run_dir), "--packet-id", "d1",
                     "--evidence", str(ev), "--diff-files", "a.py",
                     "--repo", str(tmp_path), "--branch", "nope", "--no-merge"])
    assert code == 1  # gate failed
    state = json.loads((run_dir / "mprr_state.json").read_text())
    assert "d1" not in state["running"] and "a.py" not in state["locked"]


# ── Task 5: acceptance policy wiring ──────────────────────────────────────────

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
