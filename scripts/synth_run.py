# scripts/synth_run.py
"""Autonomous synthesis driver: a resumable, file-backed state machine.

Sequences discover → select → measure → gate → (optimize) → verify. At each irreducible
agent-judgment gap it BLOCKS in an ``awaiting_*`` state with the info the agent needs, then
resumes when the agent re-invokes the matching subcommand with its input. State lives in
``synth_state.json`` + ``synth_events.jsonl`` under --run-dir — never in chat (the MPRR model).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# from -> allowed {to}.  awaiting_* are the BLOCKED states; gated_refuse/done_* are terminal.
_TRANSITIONS: dict[str, set[str]] = {
    "init": {"awaiting_hotspot"},
    "awaiting_hotspot": {"awaiting_make_input"},
    "awaiting_make_input": {"awaiting_make_input", "gated_pass", "gated_refuse", "gated_error"},
    "gated_error": {"awaiting_make_input", "done_no_win"},   # fix harness & retry, or give up
    "gated_refuse": set(),                                   # terminal: advisory only
    "gated_pass": {"awaiting_optimization", "done_no_win"},  # → optimize, or no actionable candidate
    "awaiting_optimization": {"done_win", "done_no_win"},
    "done_win": set(),
    "done_no_win": set(),
}
_BLOCKED = {"awaiting_hotspot", "awaiting_make_input", "awaiting_optimization"}


def _state_path(run_dir: Path) -> Path:
    return Path(run_dir) / "synth_state.json"


def load_state(run_dir: str | Path) -> dict[str, Any]:
    p = _state_path(run_dir)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"state": "init", "data": {}}


def _append_event(run_dir: Path, event: dict[str, Any]) -> None:
    with (Path(run_dir) / "synth_events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def transition(run_dir: str | Path, to: str, **data: Any) -> dict[str, Any]:
    run_dir = Path(run_dir)
    st = load_state(run_dir)
    frm = st["state"]
    if to not in _TRANSITIONS.get(frm, set()):
        raise ValueError(f"illegal transition {frm} -> {to}")
    st["state"] = to
    st["data"].update(data)
    run_dir.mkdir(parents=True, exist_ok=True)
    _state_path(run_dir).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    _append_event(run_dir, {"from": frm, "to": to, **data})
    return st


def status(run_dir: str | Path) -> dict[str, Any]:
    st = load_state(run_dir)
    return {"state": st["state"], "blocked": st["state"] in _BLOCKED, "data": st["data"]}
