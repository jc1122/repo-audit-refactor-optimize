# tests/test_synthesis_e2e.py
import importlib

sp = importlib.import_module("scripts.synthesize_perf")


def _summary(k, wall_tier, cv, cpu_tier):
    return {"rubric": {"dimensions": {
        "Algorithmic Scaling": {"sub_checks": {"complexity_exponent": {"k": k}}},
        "Wall-Time Stability": {"tier": wall_tier, "cv": cv},
        "CPU Efficiency": {"tier": cpu_tier},
    }}}


def test_e2e_nondegenerate_deterministic_passes(tmp_path):
    summary = _summary(1.95, "PASS", 1.5, "PASS")  # callgrind present
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    gate = sp.decide_gate(**inp)
    report = sp.write_report(out_dir=tmp_path / "perf", gate=gate, target="qsort")
    assert gate["gate"] == "pass" and gate["lane_state"] == "full"
    assert "O(n^2)" in report.read_text()


def test_e2e_degenerate_refuses(tmp_path):
    summary = _summary(0.03, "PASS", 0.4, "N/A")  # constant work, no callgrind
    gate = sp.decide_gate(**sp.extract_gate_inputs(summary, max_cv=5.0))
    sp.write_report(out_dir=tmp_path / "perf", gate=gate, target="const")
    assert gate["gate"] == "refuse" and gate["lane_state"] == "manual"
