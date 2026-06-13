# tests/test_lane_resolve.py
import importlib

lr = importlib.import_module("scripts._lane_resolve")

LANE = {"preferred": ["perf-benchmark"], "fallback": ["perf-optimization"], "manual_fallback": "x"}


def _skills(perf_benchmark_usable: bool):
    state = "usable_now" if perf_benchmark_usable else "manual_only"
    return {
        "perf-benchmark": {"state": state},
        "perf-optimization": {"state": "manual_only"},
    }


def test_no_bench_but_test_surface_and_perf_benchmark_is_synthesizable():
    profile = {"has_deterministic_perf_surface": False, "has_deterministic_test_surface": True}
    state, selected, warnings = lr._evaluate_performance_lane(LANE, _skills(True), profile)
    assert state == "synthesizable"
    assert "perf-benchmark" in selected
    assert any("synthesi" in w.lower() for w in warnings)


def test_no_bench_no_perf_benchmark_is_manual():
    profile = {"has_deterministic_perf_surface": False, "has_deterministic_test_surface": True}
    state, _selected, _warnings = lr._evaluate_performance_lane(LANE, _skills(False), profile)
    assert state == "manual"


def test_no_bench_no_test_surface_is_blocked():
    profile = {"has_deterministic_perf_surface": False, "has_deterministic_test_surface": False}
    state, _s, _w = lr._evaluate_performance_lane(LANE, _skills(True), profile)
    assert state == "blocked"
