"""Dogfood guard: running the orchestrator's own detectors on its own repo must be honest."""
import importlib
import json
from pathlib import Path

checker = importlib.import_module("scripts.check_skill_requirements")
lr = importlib.import_module("scripts._lane_resolve")
probe = importlib.import_module("scripts._skill_probe")
wave = importlib.import_module("scripts.run_diagnosis_wave")

REPO = Path(__file__).resolve().parents[1]


def test_repo_b_has_no_false_benchmark_surface():
    # G1: scripts/graduate_benchmark.py + tests/test_graduate_benchmark.py must NOT count.
    profile = checker.scan_repo_profile(REPO)
    assert profile["benchmark_surfaces"] == []
    assert profile["has_deterministic_perf_surface"] is False


def test_repo_b_performance_lane_resolves_synthesizable():
    # G1 end-to-end: real repo-B profile + perf-benchmark usable → synthesizable.
    profile = checker.scan_repo_profile(REPO)
    assert profile["has_deterministic_test_surface"] is True  # repo-B has pytest
    lane = {"preferred": ["perf-benchmark"], "fallback": ["perf-optimization"],
            "manual_fallback": "manual perf reasoning"}
    skills = {"perf-benchmark": {"state": "usable_now"},
              "perf-optimization": {"state": "manual_only"}}
    state, selected, _warnings = lr._evaluate_performance_lane(lane, skills, profile)
    assert state == "synthesizable"
    assert "perf-benchmark" in selected


def test_repo_b_orchestration_process_skills_are_always_available():
    # G4: the manifest flags the process skills, and the probe resolves them usable.
    manifest = json.loads((REPO / "scripts" / "skill_bootstrap_manifest.json").read_text())
    for name in ("verification-before-completion", "dispatching-parallel-agents",
                 "subagent-driven-development"):
        cfg = manifest["skills"][name]
        assert cfg.get("always_available") is True, name
        entry = probe._skill_entry(name, cfg, usable_skills={}, advisory_skills={})
        assert entry["state"] == "usable_now", name


def test_wave_excludes_tests_and_fixtures_by_default():
    # G2: an unscoped wave defaults to excluding tests/ and fixtures.
    assert wave._effective_excludes(source_prefixes=[], exclude_prefixes=[]) == ["tests", "fixtures"]
    args = wave._audit_scope_args([], ["tests", "fixtures"], supports_exclude=True)
    assert args.count("--exclude-prefix") == 2 and "tests" in args and "fixtures" in args
