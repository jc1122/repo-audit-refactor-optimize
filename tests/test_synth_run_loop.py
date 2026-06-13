# tests/test_synth_run_loop.py
import importlib, json
from pathlib import Path

sr = importlib.import_module("scripts.synth_run")


def test_discover_blocks_awaiting_hotspot(tmp_path):
    cj = tmp_path / "c.json"
    cj.write_text(json.dumps([{"id": "h1", "function": "a.py:1:f", "cumulative_s": 0.9}]))
    rc = sr.main(["discover", "--run-dir", str(tmp_path), "--candidates-json", str(cj)])
    assert rc == 0
    s = sr.status(tmp_path)
    assert s["state"] == "awaiting_hotspot" and s["blocked"] is True
    assert s["data"]["candidates"][0]["id"] == "h1"


def _to_gated_pass(tmp_path):
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.transition(tmp_path, "awaiting_make_input")
    sr.transition(tmp_path, "gated_pass", gate={"gate": "pass"})


def test_candidate_with_selection_blocks_awaiting_optimization(tmp_path):
    _to_gated_pass(tmp_path)
    sel = tmp_path / "sel.json"
    sel.write_text(json.dumps({"status": "selected", "path": "a.py", "signal": "PERF"}))
    rc = sr.main(["candidate", "--run-dir", str(tmp_path), "--selection-json", str(sel)])
    assert rc == 0 and sr.status(tmp_path)["state"] == "awaiting_optimization"
    assert sr.load_state(tmp_path)["data"]["candidate"]["path"] == "a.py"


def test_candidate_no_candidates_is_terminal(tmp_path):
    _to_gated_pass(tmp_path)
    sel = tmp_path / "sel.json"
    sel.write_text(json.dumps({"status": "no_candidates"}))
    rc = sr.main(["candidate", "--run-dir", str(tmp_path), "--selection-json", str(sel)])
    assert rc == 1 and sr.status(tmp_path)["state"] == "done_no_win"


def _to_awaiting_opt(tmp_path):
    _to_gated_pass(tmp_path)
    sr.transition(tmp_path, "awaiting_optimization", candidate={"path": "a.py"})


def test_verify_accept_is_done_win(tmp_path):
    _to_awaiting_opt(tmp_path)
    vj = tmp_path / "v.json"; vj.write_text(json.dumps({"verdict": "accept"}))
    rc = sr.main(["verify", "--run-dir", str(tmp_path), "--verdict-json", str(vj)])
    assert rc == 0 and sr.status(tmp_path)["state"] == "done_win"


def test_verify_reject_is_done_no_win_with_revert(tmp_path):
    _to_awaiting_opt(tmp_path)
    vj = tmp_path / "v.json"; vj.write_text(json.dumps({"verdict": "reject", "reasons": ["median"]}))
    rc = sr.main(["verify", "--run-dir", str(tmp_path), "--verdict-json", str(vj)])
    assert rc == 1
    st = sr.load_state(tmp_path)
    assert st["state"] == "done_no_win" and st["data"]["decision"]["revert"] is True
