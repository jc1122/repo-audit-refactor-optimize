# tests/test_synth_run_state.py
import importlib
import pytest

sr = importlib.import_module("scripts.synth_run")


def test_initial_state_is_init(tmp_path):
    assert sr.load_state(tmp_path)["state"] == "init"


def test_legal_transition_persists_and_logs(tmp_path):
    sr.transition(tmp_path, "awaiting_hotspot", candidates=[{"id": "h1"}])
    st = sr.load_state(tmp_path)
    assert st["state"] == "awaiting_hotspot"
    assert st["data"]["candidates"] == [{"id": "h1"}]
    events = (tmp_path / "synth_events.jsonl").read_text().splitlines()
    assert events and '"to": "awaiting_hotspot"' in events[-1]


def test_illegal_transition_raises(tmp_path):
    with pytest.raises(ValueError):
        sr.transition(tmp_path, "done_win")  # from init, not allowed


def test_state_is_resumable_across_processes(tmp_path):
    sr.transition(tmp_path, "awaiting_hotspot")
    sr.transition(tmp_path, "awaiting_make_input", target="find_max")
    # a fresh "process" only reads the file
    st = sr.load_state(tmp_path)
    assert st["state"] == "awaiting_make_input" and st["data"]["target"] == "find_max"


def test_terminal_states_have_no_outgoing(tmp_path):
    assert sr._TRANSITIONS["gated_refuse"] == set()
    assert sr._TRANSITIONS["done_win"] == set()
