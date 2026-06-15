"""Gate-integrity self-audit: class-level invariants on the orchestrator itself.

These assert tooling BEHAVIOUR (#4/#11), not target source — the net no leaf can
be. They generalize the single-instance Wave-A regressions into class-level
invariants so the gap classes (errored-lane-passes, lane-not-scoped) cannot recur.
"""

import importlib
import json

import pytest

rdw = importlib.import_module("scripts.run_diagnosis_wave")


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
