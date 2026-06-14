"""Orchestrator-facing CLI. Stdlib only. State lives on disk, never in chat."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Imports follow the sys.path bootstrap above (lets the CLI run as a script).
from scripts import mprr_gate, mprr_integrate, mprr_normalize, mprr_packets  # noqa: E402
from scripts.mprr_schedule import SaturatingScheduler  # noqa: E402


def _load(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    return json.loads(Path(path).read_text())


def _items(findings_path: str | None, triage_path: str | None) -> list[Any]:
    items = mprr_normalize.normalize(_load(findings_path))
    items += mprr_normalize.from_triage_report(_load(triage_path))
    return sorted(items, key=lambda it: it.id)


def _log(run_dir: Path, event: dict[str, Any]) -> None:
    with (run_dir / "mprr_events.jsonl").open("a") as fh:
        fh.write(json.dumps(event) + "\n")


def _read_state(run_dir: Path) -> dict[str, Any]:
    p = run_dir / "mprr_state.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"running": {}, "locked": []}


def _write_state(
    run_dir: Path, running: dict[str, list[str]], locked: set[str]
) -> None:
    (run_dir / "mprr_state.json").write_text(
        json.dumps({"running": running, "locked": sorted(locked)}, indent=2)
    )


def _cmd_plan(a: argparse.Namespace) -> int:
    run_dir = Path(a.run_dir)
    items = _items(a.findings, a.triage)
    by_id = {it.id: it for it in items}
    state = _read_state(run_dir)
    running: dict[str, list[str]] = dict(state["running"])
    locked: set[str] = set(state["locked"])
    pending = [it for it in items if it.id not in running]
    sched = SaturatingScheduler(pending, ceiling=a.ceiling)
    # seed scheduler with already-running locks by lowering effective room
    sched._locked = set(locked)  # noqa: SLF001 (deliberate seed)
    sched._running = {k: by_id.get(k) for k in running}  # noqa: SLF001
    batch = sched.dispatchable()
    packets = []
    for it in batch:
        running[it.id] = list(it.files)
        locked |= set(it.files)
        packets.append(
            mprr_packets.remediation_packet(it, repo=a.repo or "", lessons=[])
        )
        _log(run_dir, {"event": "start", "id": it.id, "files": list(it.files)})
    _write_state(run_dir, running, locked)
    print(json.dumps(packets, indent=2))
    return 0


def _cmd_integrate(a: argparse.Namespace) -> int:
    run_dir = Path(a.run_dir)
    state = _read_state(run_dir)
    running: dict[str, list[str]] = dict(state["running"])
    locked: set[str] = set(state["locked"])
    files = running.get(a.packet_id, [])
    evidence = json.loads(Path(a.evidence).read_text())
    diff_files = [f for f in (a.diff_files or "").split(",") if f]
    rc = evidence.get("remediation_class") or _class_of(a, run_dir)
    scope_ok, scope_reasons = mprr_integrate.assert_scope(files, diff_files)
    gate_ok, gate_reasons = mprr_gate.verify(rc, evidence)
    guard_ok, guard_reasons = mprr_integrate.self_guard(a.repo, diff_files)
    merged = False
    status = "discard"
    if scope_ok and gate_ok and guard_ok:
        if not a.no_merge:
            mprr_integrate.merge_clean(a.repo, a.branch)  # raises on conflict
        merged = True
        status = "merge"
    # always release locks (complete)
    running.pop(a.packet_id, None)
    locked -= set(files)
    _write_state(run_dir, running, locked)
    _log(
        run_dir,
        {
            "event": status,
            "id": a.packet_id,
            "conflict": False,
            "merged": merged,
            "reasons": scope_reasons + gate_reasons + guard_reasons,
        },
    )
    return 0 if merged else 1


def _class_of(a: argparse.Namespace, run_dir: Path) -> str:
    # remediation_class is carried in the evidence; fall back to "mechanical"
    return "mechanical"


def _cmd_reaudit(a: argparse.Namespace) -> int:
    return len(
        _items(a.findings, a.triage)
    )  # exit code = residual count (0 = converged)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mprr_run")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--findings")
    sp.add_argument("--triage")
    sp.add_argument("--ceiling", type=int, default=8)
    sp.add_argument("--repo", default="")
    sp.set_defaults(fn=_cmd_plan)

    si = sub.add_parser("integrate")
    si.add_argument("--run-dir", required=True)
    si.add_argument("--packet-id", required=True)
    si.add_argument("--evidence", required=True)
    si.add_argument("--diff-files", default="")
    si.add_argument("--repo", default=".")
    si.add_argument("--branch", default="")
    si.add_argument("--no-merge", action="store_true")
    si.set_defaults(fn=_cmd_integrate)

    sr = sub.add_parser("reaudit")
    sr.add_argument("--findings")
    sr.add_argument("--triage")
    sr.set_defaults(fn=_cmd_reaudit)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
