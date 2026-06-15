"""Gate-integrity self-audit: class-level invariants on the orchestrator itself.

These assert tooling BEHAVIOUR (#4/#11), not target source — the net no leaf can
be. They generalize the single-instance Wave-A regressions into class-level
invariants so the gap classes (errored-lane-passes, lane-not-scoped) cannot recur.
"""

import importlib
import json

import pytest

cwb = importlib.import_module("scripts.check_wave_baseline")
rdw = importlib.import_module("scripts.run_diagnosis_wave")

ALL_LANES = list(
    json.loads(rdw._DEFAULT_REGISTRY.read_text(encoding="utf-8"))["lanes"]
)
LANE_NAMES = [lane["name"] for lane in ALL_LANES]


# ── Task B1: parametrized errored-lane invariant (#4) ──────────────────


@pytest.mark.parametrize("errored", LANE_NAMES)
def test_gate_fails_when_any_single_lane_errors(tmp_path, capsys, errored):
    summary = {n: {"exit": 0, "status": "ok", "findings": 0} for n in LANE_NAMES}
    summary[errored] = {"exit": 2, "status": "error", "findings": 0}
    snap = tmp_path / "a.json"
    s = tmp_path / "s.json"
    snap.write_text("[]")
    s.write_text(json.dumps(summary))
    rc = cwb.main(["--snapshot", str(snap), "--summary", str(s)])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "lane_error"


# ── Task B2: lane-scoping invariant (#11) ──────────────────────────────


def test_every_source_scoped_lane_receives_source_prefix(tmp_path):
    ctx = rdw._LaneContext(
        repo=tmp_path, out_root=tmp_path, source_prefixes=["scripts"],
        exclude_prefixes=[], rev=None, coverage_json=None,
        security_config=None, hotspot_config=None)
    for lane in rdw.SOURCE_SCOPED_LANES:
        cmd: list[str] = []
        rdw._append_scope_args(cmd, lane, tmp_path / "leaf.py", ctx)
        assert "--source-prefix" in cmd and "scripts" in cmd, lane


def test_registry_source_scoped_flag_matches_code():
    reg = json.loads(rdw._DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    flagged = {lane["name"] for lane in reg["lanes"] if lane.get("source_scoped")}
    assert flagged == rdw.SOURCE_SCOPED_LANES
