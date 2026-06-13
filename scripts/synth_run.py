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


from scripts import synthesize_perf as _gate


# synth_microbench lives in perf-benchmark-skill; import by path so the driver stays repo-local.
def _load_synth_microbench():
    import importlib.util, os
    root = os.environ.get("PERF_BENCHMARK_ROOT", str(Path.home() / "projects" / "perf-benchmark-skill"))
    spec = importlib.util.spec_from_file_location("synth_microbench", Path(root) / "scripts" / "synth_microbench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _cmd_select(a: argparse.Namespace) -> int:
    sm = _load_synth_microbench()
    perf_dir = Path(a.run_dir) / "perf" / a.name
    res = sm.generate(out_dir=perf_dir, name=a.name, import_root=Path(a.import_root),
                      module=a.module, func=a.func)
    transition(a.run_dir, "awaiting_make_input", hotspot=a.hotspot, target=a.name,
               harness_dir=str(perf_dir), make_input=str(res["make_input"]),
               target_command=res["target_command"],
               note=f"Author make_input(size) at {res['make_input']}, then run `measure`.")
    return 0


def _cmd_measure(a: argparse.Namespace) -> int:
    sm = _load_synth_microbench()
    st = load_state(a.run_dir)
    harness = Path(st["data"]["harness_dir"])
    guard = sm.validate_make_input(harness)
    if not guard["ok"]:
        # stay blocked at awaiting_make_input with the reason — never advance on a bad harness
        transition(a.run_dir, "awaiting_make_input", make_input_check=guard,
                   note=f"make_input not ready: {guard['reason']}")
        print(json.dumps(guard, indent=2))
        return 1
    summary = json.loads(Path(a.summary).read_text())
    gate = _gate.decide_gate(**_gate.extract_gate_inputs(summary, max_cv=a.max_cv))
    _gate.write_report(out_dir=harness, gate=gate, target=st["data"]["target"])
    if gate["gate"] == "pass":
        transition(a.run_dir, "gated_pass", gate=gate)
        return 0
    if gate["gate"] == "refuse":
        transition(a.run_dir, "gated_refuse", gate=gate)  # terminal advisory
        return 1
    # gate == "error": bump attempts, retry or stop
    attempts = int(st["data"].get("attempts", 0)) + 1
    transition(a.run_dir, "gated_error", gate=gate, attempts=attempts)
    if attempts > a.max_attempts:  # allow up to --max-attempts retries, then give up
        transition(a.run_dir, "done_no_win", reason=f"gave up after {attempts} failed measurements")
    else:
        transition(a.run_dir, "awaiting_make_input", note="measurement error; fix the harness and retry")
    return 2


def _cmd_status(a: argparse.Namespace) -> int:
    print(json.dumps(status(a.run_dir), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Autonomous synthesis driver.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("select"); s.set_defaults(fn=_cmd_select)
    s.add_argument("--run-dir", required=True)
    s.add_argument("--hotspot", required=True)
    s.add_argument("--import-root", required=True)
    s.add_argument("--module", required=True)
    s.add_argument("--func", required=True)
    s.add_argument("--name", required=True)

    m = sub.add_parser("measure"); m.set_defaults(fn=_cmd_measure)
    m.add_argument("--run-dir", required=True)
    m.add_argument("--summary", required=True, help="benchmark_summary.json from the pipeline")
    m.add_argument("--max-cv", type=float, default=5.0)
    m.add_argument("--max-attempts", type=int, default=3)

    st = sub.add_parser("status"); st.set_defaults(fn=_cmd_status)
    st.add_argument("--run-dir", required=True)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
