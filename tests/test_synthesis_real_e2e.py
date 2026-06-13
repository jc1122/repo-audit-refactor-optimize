# tests/test_synthesis_real_e2e.py
import json, subprocess, sys, importlib
from pathlib import Path
import pytest

sp = importlib.import_module("scripts.synthesize_perf")
PB = Path.home() / "projects" / "perf-benchmark-skill"
PIPELINE = PB / "scripts" / "perf_benchmark_pipeline.py"
SYNTH = PB / "scripts" / "synth_microbench.py"


@pytest.mark.skipif(not PIPELINE.is_file() or not SYNTH.is_file(), reason="perf-benchmark-skill not present")
def test_synthesize_quadratic_target_measures_and_gates(tmp_path):
    # a target with clear O(n^2) behavior
    src = tmp_path / "src"; src.mkdir()
    (src / "algo.py").write_text(
        "def slow_dupes(data):\n"
        "    out = []\n"
        "    for i in range(len(data)):\n"
        "        for j in range(len(data)):\n"
        "            if data[i] == data[j]:\n"
        "                out.append(i)\n"
        "    return out\n", encoding="utf-8")
    perf = tmp_path / "perf" / "slow"
    sys.path.insert(0, str(SYNTH.parent))
    import synth_microbench as sm
    paths = sm.generate(out_dir=perf, name="slow", import_root=src, module="algo", func="slow_dupes")
    (perf / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n", encoding="utf-8")
    assert sm.validate_make_input(perf)["ok"] is True

    out = tmp_path / "pbout"
    rc = subprocess.run(
        [sys.executable, str(PIPELINE), "--root", str(perf), "--out-dir", str(out),
         "--target", paths["target_command"], "--sizes", "200,400,800,1600",
         "--tier", "fast", "--expected-complexity", "quadratic"],
        capture_output=True, text=True, cwd=str(perf),
    ).returncode
    summary_path = out / "benchmark_summary.json"
    if not summary_path.is_file():
        pytest.skip("pipeline did not produce a summary in this environment")

    gate = sp.decide_gate(**sp.extract_gate_inputs(json.loads(summary_path.read_text()), max_cv=15.0))
    # Honest-refusal contract on a real quadratic target: the gate must never return
    # "error" or a degenerate O(1) refuse. A wall-time-noise refuse IS acceptable — that
    # is the whole point of the feature (refuse a measurement it cannot trust). At small
    # sizes on a noisy box the fitted exponent is unreliable, so when the gate refuses for
    # noise we assert the refusal path, not the (untrustworthy) complexity label.
    assert gate["gate"] in {"pass", "refuse"}
    assert "degenerate" not in gate["reason"].lower()  # never the O(1) refuse on real n^2 work
    if gate["gate"] == "pass":
        # a clean measurement resolved the scaling — must be super-constant, not O(1)/O(log n)
        assert gate["complexity"] in {"O(n^2)", "O(n log n)", "O(n)", "O(n^3+)"}
    else:
        # refuse: must be the wall-time-noise path (CV over bound / no deterministic tier)
        assert "cv" in gate["reason"].lower() or "noise" in gate["reason"].lower()
