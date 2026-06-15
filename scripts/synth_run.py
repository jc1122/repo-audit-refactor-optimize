# scripts/synth_run.py
"""Autonomous synthesis driver: a resumable, file-backed state machine.

Sequences discover → select → measure → gate → (optimize) → verify. At each
irreducible agent-judgment gap it BLOCKS in an ``awaiting_*`` state with the info
the agent needs, then resumes when the agent re-invokes the matching subcommand
with its input. State lives in ``synth_state.json`` + ``synth_events.jsonl`` under
--run-dir — never in chat (the MPRR model).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))  # let the driver run as a direct script

# from -> allowed {to}.  awaiting_* are the BLOCKED states;
# gated_refuse/done_* are terminal.
_TRANSITIONS: dict[str, set[str]] = {
    "init": {"awaiting_hotspot"},
    "awaiting_hotspot": {"awaiting_make_input"},
    "awaiting_make_input": {
        "awaiting_make_input",
        "gated_pass",
        "gated_refuse",
        "gated_error",
    },
    "gated_error": {
        "awaiting_make_input",
        "done_no_win",
    },  # fix harness & retry, or give up
    "gated_refuse": set(),  # terminal: advisory only
    "gated_pass": {
        "awaiting_optimization",
        "done_no_win",
    },  # → optimize, or no actionable candidate
    "awaiting_optimization": {"done_win", "done_no_win"},
    "done_win": set(),
    "done_no_win": set(),
}
_BLOCKED = {"awaiting_hotspot", "awaiting_make_input", "awaiting_optimization"}


def _state_path(run_dir: str | Path) -> Path:
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
    return {
        "state": st["state"],
        "blocked": st["state"] in _BLOCKED,
        "data": st["data"],
    }


# Deferred import (after the state helpers) to avoid an import cycle.
from scripts import synthesize_perf as _gate  # noqa: E402


# synth_microbench lives in perf-benchmark-skill; import by path so the driver
# stays repo-local.
def _load_synth_microbench():
    import importlib.util
    import os

    root = os.environ.get(
        "PERF_BENCHMARK_ROOT", str(Path.home() / "projects" / "perf-benchmark-skill")
    )
    spec = importlib.util.spec_from_file_location(
        "synth_microbench", Path(root) / "scripts" / "synth_microbench.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _cmd_select(a: argparse.Namespace) -> int:
    sm = _load_synth_microbench()
    perf_dir = Path(a.run_dir) / "perf" / a.name
    res = sm.generate(
        out_dir=perf_dir,
        name=a.name,
        import_root=Path(a.import_root),
        module=a.module,
        func=a.func,
    )
    transition(
        a.run_dir,
        "awaiting_make_input",
        hotspot=a.hotspot,
        target=a.name,
        harness_dir=str(perf_dir),
        make_input=str(res["make_input"]),
        target_command=res["target_command"],
        note=f"Author make_input(size) at {res['make_input']}, then run `measure`.",
    )
    return 0


def _cmd_measure(a: argparse.Namespace) -> int:
    sm = _load_synth_microbench()
    st = load_state(a.run_dir)
    harness = Path(st["data"]["harness_dir"])
    guard = sm.validate_make_input(harness)
    if not guard["ok"]:
        # stay blocked at awaiting_make_input with the reason —
        # never advance on a bad harness
        transition(
            a.run_dir,
            "awaiting_make_input",
            make_input_check=guard,
            note=f"make_input not ready: {guard['reason']}",
        )
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
        transition(
            a.run_dir,
            "done_no_win",
            reason=f"gave up after {attempts} failed measurements",
        )
    else:
        transition(
            a.run_dir,
            "awaiting_make_input",
            note="measurement error; fix the harness and retry",
        )
    return 2


def _cmd_status(a: argparse.Namespace) -> int:
    print(json.dumps(status(a.run_dir), indent=2))
    return 0


def _load_by_path(modname: str, relpath: str):
    import importlib.util
    import os

    root = os.environ.get(
        "PERF_BENCHMARK_ROOT", str(Path.home() / "projects" / "perf-benchmark-skill")
    )
    spec = importlib.util.spec_from_file_location(modname, Path(root) / relpath)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {modname} from {relpath}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cmd_discover(a: argparse.Namespace) -> int:
    if a.candidates_json:  # injected (tests / pre-computed)
        candidates = json.loads(Path(a.candidates_json).read_text())
    else:  # run the stdlib profiler
        pd = _load_by_path("profile_discover", "scripts/profile_discover.py")
        ranked = Path(a.run_dir) / "perf" / "discovery" / "profile_ranked.json"
        ranked.parent.mkdir(parents=True, exist_ok=True)
        pd.main(["--script", a.script, "--out", str(ranked), "--top", str(a.top)])
        data = json.loads(ranked.read_text()) if ranked.is_file() else []
        candidates = (
            data if isinstance(data, list) else []
        )  # {"error":…} → no candidates
    if a.smells_json and Path(a.smells_json).is_file():  # merge static smells
        candidates += [
            {"id": f"smell:{s.get('id', '?')}", **s}
            for s in json.loads(Path(a.smells_json).read_text())
        ]
    transition(
        a.run_dir,
        "awaiting_hotspot",
        candidates=candidates,
        note="Pick a hotspot id from candidates, then run `select`.",
    )
    return 0


def _cmd_candidate(a: argparse.Namespace) -> int:
    if a.selection_json:  # injected select_candidate result
        result = json.loads(Path(a.selection_json).read_text())
    else:
        sc = _load_by_path(
            "select_candidate", "perf-optimization/scripts/select_candidate.py"
        )
        result = sc.select_candidate(json.loads(Path(a.findings_json).read_text()))
    if result.get("status") == "no_candidates":
        transition(
            a.run_dir,
            "done_no_win",
            reason="gate-quality benchmark but no actionable PERF candidate",
        )
        print(json.dumps(result, indent=2))
        return 1
    transition(
        a.run_dir,
        "awaiting_optimization",
        candidate=result,
        note=(
            "Apply the candidate change, re-run the pipeline for an "
            "after-summary, then `verify`."
        ),
    )
    return 0


def _cmd_verify(a: argparse.Namespace) -> int:
    if a.verdict_json:  # injected verify_win verdict
        verdict = json.loads(Path(a.verdict_json).read_text())
    else:
        vw = _load_by_path("verify_win", "perf-optimization/scripts/verify_win.py")
        out = Path(a.run_dir) / "perf" / "verdict.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        vw.main(
            [
                "--before",
                a.before,
                "--after",
                a.after,
                "--suite-exit-code",
                str(a.suite_exit_code),
                "--out",
                str(out),
            ]
        )
        verdict = json.loads(out.read_text())
    decision = _gate.verify_and_decide(
        verdict=verdict
    )  # never trusts a self-reported win
    target = "done_win" if decision["outcome"] == "done_win" else "done_no_win"
    transition(a.run_dir, target, verdict=verdict, decision=decision)
    print(json.dumps(decision, indent=2))
    return 0 if target == "done_win" else 1


def _add_core_parsers(sub) -> None:
    """Register the discover/select/measure/status subcommands."""
    s = sub.add_parser("select")
    s.set_defaults(fn=_cmd_select)
    s.add_argument("--run-dir", required=True)
    s.add_argument("--hotspot", required=True)
    s.add_argument("--import-root", required=True)
    s.add_argument("--module", required=True)
    s.add_argument("--func", required=True)
    s.add_argument("--name", required=True)

    m = sub.add_parser("measure")
    m.set_defaults(fn=_cmd_measure)
    m.add_argument("--run-dir", required=True)
    m.add_argument(
        "--summary", required=True, help="benchmark_summary.json from the pipeline"
    )
    m.add_argument("--max-cv", type=float, default=5.0)
    m.add_argument("--max-attempts", type=int, default=3)

    st = sub.add_parser("status")
    st.set_defaults(fn=_cmd_status)
    st.add_argument("--run-dir", required=True)


def _add_perf_parsers(sub) -> None:
    """Register the discover/candidate/verify subcommands."""
    d = sub.add_parser("discover")
    d.set_defaults(fn=_cmd_discover)
    d.add_argument("--run-dir", required=True)
    d.add_argument(
        "--script",
        default=None,
        help="Representative script to profile (omit with --candidates-json)",
    )
    d.add_argument(
        "--candidates-json", default=None, help="Pre-computed candidates (inject)"
    )
    d.add_argument(
        "--smells-json", default=None, help="perf-smell findings to merge as candidates"
    )
    d.add_argument("--top", type=int, default=20)

    c = sub.add_parser("candidate")
    c.set_defaults(fn=_cmd_candidate)
    c.add_argument("--run-dir", required=True)
    c.add_argument(
        "--findings-json", default=None, help="PERF findings for select_candidate"
    )
    c.add_argument(
        "--selection-json",
        default=None,
        help="Pre-computed select_candidate result (inject)",
    )

    v = sub.add_parser("verify")
    v.set_defaults(fn=_cmd_verify)
    v.add_argument("--run-dir", required=True)
    v.add_argument(
        "--verdict-json", default=None, help="Pre-computed verify_win verdict (inject)"
    )
    v.add_argument("--before", default=None)
    v.add_argument("--after", default=None)
    v.add_argument("--suite-exit-code", type=int, default=0)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Autonomous synthesis driver.")
    sub = p.add_subparsers(dest="cmd", required=True)
    _add_core_parsers(sub)
    _add_perf_parsers(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
