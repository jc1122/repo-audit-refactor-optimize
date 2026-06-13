# tests/test_synth_run_cli.py
import importlib, json, types
from pathlib import Path
import pytest

sr = importlib.import_module("scripts.synth_run")


@pytest.fixture(autouse=True)
def _stub_synth_microbench(monkeypatch):
    """Stub the cross-repo synth_microbench load so the driver's state logic is hermetic.
    The REAL generator/validator is tested in perf-benchmark-skill's own suite (A2); here we
    only exercise synth_run's transitions, so depending on ~/projects/perf-benchmark-skill
    (absent in repo-B CI) would be a false failure."""
    fake = types.SimpleNamespace()

    def generate(*, out_dir, name, import_root, module, func):
        out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        mi = out_dir / "make_input.py"
        mi.write_text("def make_input(size):\n    raise NotImplementedError\n", encoding="utf-8")
        bench = out_dir / f"bench_{name}.py"; bench.write_text("x\n", encoding="utf-8")
        return {"make_input": str(mi), "bench": str(bench),
                "target_command": f"python3 bench_{name}.py {{SIZE}}", "spec": {}}

    def validate_make_input(harness_dir, **_k):
        txt = (Path(harness_dir) / "make_input.py").read_text(encoding="utf-8")
        return ({"ok": False, "reason": "make_input is still the stub"}
                if "NotImplementedError" in txt else {"ok": True, "reason": "scales"})

    fake.generate = generate
    fake.validate_make_input = validate_make_input
    monkeypatch.setattr(sr, "_load_synth_microbench", lambda: fake)


def _summary(k, cpu_tier="PASS", wall_tier="PASS", cv=1.0):
    return {"complexity_exponent": k, "deterministic_tier": cpu_tier != "N/A",
            "rubric": {"dimensions": {"Wall-Time Stability": {"tier": wall_tier, "cv": cv},
                                      "CPU Efficiency": {"tier": cpu_tier}}}}


def test_select_blocks_awaiting_make_input(tmp_path):
    sr.transition(tmp_path, "awaiting_hotspot", candidates=[{"id": "h1", "function": "algo.py:1:f"}])
    rc = sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
                  "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    assert rc == 0
    assert sr.status(tmp_path)["state"] == "awaiting_make_input"
    assert sr.status(tmp_path)["blocked"] is True


def test_measure_blocks_when_make_input_unfilled(tmp_path):
    # synthesize first so the stub exists
    (tmp_path / "src").mkdir()
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
             "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    s = _summary(1.9)
    sp_path = tmp_path / "s.json"; sp_path.write_text(json.dumps(s))
    rc = sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(sp_path)])
    # the cheap guard fires: stub still raises NotImplementedError → stays blocked, NOT measured
    assert rc != 0
    assert sr.status(tmp_path)["state"] == "awaiting_make_input"
    assert "make_input" in json.dumps(sr.status(tmp_path)["data"]).lower()


def test_measure_passes_gate_when_inputs_ready(tmp_path):
    (tmp_path / "src").mkdir()
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
             "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    harness = Path(sr.load_state(tmp_path)["data"]["harness_dir"])
    (harness / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n")
    sp_path = tmp_path / "s.json"; sp_path.write_text(json.dumps(_summary(1.9)))
    rc = sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(sp_path)])
    assert rc == 0
    assert sr.status(tmp_path)["state"] == "gated_pass"


def test_measure_error_increments_attempts_and_stops_after_max(tmp_path):
    (tmp_path / "src").mkdir()
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.main(["select", "--run-dir", str(tmp_path), "--hotspot", "h1",
             "--import-root", str(tmp_path / "src"), "--module", "algo", "--func", "f", "--name", "f"])
    harness = Path(sr.load_state(tmp_path)["data"]["harness_dir"])
    (harness / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n")
    err = tmp_path / "err.json"
    err.write_text(json.dumps({"rubric": {"dimensions": {"Algorithmic Scaling": {"tier": "N/A"}}}}))
    # first error → back to awaiting_make_input; with --max-attempts 1 the second gives up
    sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(err), "--max-attempts", "1"])
    assert sr.status(tmp_path)["state"] == "awaiting_make_input"
    (harness / "make_input.py").write_text("def make_input(size):\n    return list(range(size))\n")
    sr.main(["measure", "--run-dir", str(tmp_path), "--summary", str(err), "--max-attempts", "1"])
    assert sr.status(tmp_path)["state"] == "done_no_win"  # stop-condition hit
