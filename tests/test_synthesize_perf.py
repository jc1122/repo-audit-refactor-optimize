# tests/test_synthesize_perf.py
import importlib

sp = importlib.import_module("scripts.synthesize_perf")


def test_decide_gate_pass_on_deterministic_nondegenerate():
    g = sp.decide_gate(exponent=1.0, deterministic=True, wall_cv_ok=False)
    assert g["gate"] == "pass"
    assert g["lane_state"] == "full"


def test_decide_gate_pass_on_wall_time_within_cv():
    g = sp.decide_gate(exponent=2.0, deterministic=False, wall_cv_ok=True)
    assert g["gate"] == "pass"


def test_decide_gate_refuses_degenerate_constant_work():
    g = sp.decide_gate(exponent=0.02, deterministic=True, wall_cv_ok=True)
    assert g["gate"] == "refuse"
    assert "degenerate" in g["reason"].lower()
    assert g["lane_state"] == "manual"


def test_decide_gate_refuses_noisy_nondeterministic():
    g = sp.decide_gate(exponent=1.0, deterministic=False, wall_cv_ok=False)
    assert g["gate"] == "refuse"
    assert "noise" in g["reason"].lower() or "cv" in g["reason"].lower()


def test_decide_gate_errors_when_not_measured():
    # failed/insufficient measurement is an ERROR (fix harness), never a degenerate refuse
    g = sp.decide_gate(exponent=0.0, deterministic=False, wall_cv_ok=False, measured=False)
    assert g["gate"] == "error"
    assert g["lane_state"] == "manual"
    assert "fix the harness" in g["reason"].lower()


def test_extract_inputs_prefers_top_level_contract():
    # Track A4: perf-benchmark exposes a stable top-level contract
    summary = {"complexity_exponent": 1.9, "deterministic_tier": True,
               "rubric": {"dimensions": {"Wall-Time Stability": {"tier": "PASS", "cv": 2.1}}}}
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    assert inp == {"exponent": 1.9, "deterministic": True, "wall_cv_ok": True, "measured": True}


def test_extract_inputs_falls_back_to_rubric_internals():
    summary = {"rubric": {"dimensions": {
        "Algorithmic Scaling": {"sub_checks": {"complexity_exponent": {"k": 1.9}}},
        "Wall-Time Stability": {"tier": "PASS", "cv": 2.1},
        "CPU Efficiency": {"tier": "PASS"},
    }}}
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    assert inp["exponent"] == 1.9 and inp["deterministic"] is True and inp["measured"] is True


def test_extract_inputs_unmeasured_when_no_exponent():
    # pipeline failure → Algorithmic Scaling N/A, no exponent anywhere → measured False
    summary = {"rubric": {"dimensions": {
        "Algorithmic Scaling": {"tier": "N/A", "note": "Insufficient data"},
        "Wall-Time Stability": {"tier": "N/A"},
    }}}
    inp = sp.extract_gate_inputs(summary, max_cv=5.0)
    assert inp["measured"] is False
    assert sp.decide_gate(**inp)["gate"] == "error"


def test_main_handles_unreadable_summary(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not json", encoding="utf-8")
    rc = sp.main(["--summary", str(bad), "--out-dir", str(tmp_path / "perf"), "--target", "x"])
    assert rc == 2
    assert (tmp_path / "perf" / "synthesis_report.md").exists()


def test_write_report_renders_each_verdict(tmp_path):
    for state, marker in [("pass", "gate pass"), ("refuse", "honest refusal"), ("error", "measurement error")]:
        res = sp.write_report(
            out_dir=tmp_path / state,
            gate={"gate": state, "reason": "r", "lane_state": "manual", "complexity": "O(1)", "deterministic": True},
            target="t",
        )
        assert marker in res.read_text().lower()
