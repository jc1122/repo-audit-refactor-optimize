#!/usr/bin/env python3
"""Convergence gate: diagnosis wave on this repo (Option A — trust the wave partition).

The wave auto-suppresses `<repo>/.repo-audit/accept.json` entries at the report stage,
writing the active set to `wave_findings.json` and the accept partition to
`wave_findings.accepted.json` (`{"accepted":[...], "stale":[...]}`). Convergence is:

    pass  iff  the active set is EMPTY  AND  the accepted sidecar's stale list is empty.

A non-empty active set means a finding is not covered by accept.json (a new residual);
a non-empty stale list means an accept entry matched nothing (drop it from the file).
"""

import argparse
import importlib
import json
import os
import subprocess  # nosec B404: local trusted wave runner
import sys
from pathlib import Path

_wf = importlib.import_module(
    "scripts._wave_findings" if __package__ else "_wave_findings"
)

REPO = Path(__file__).resolve().parents[1]
WAVE_ANCHOR = Path(__file__).with_name("wave_anchor.txt")
SECURITY_CONFIG = Path(__file__).with_name("security_audit_config.json")
HOTSPOT_CONFIG = Path(__file__).with_name("hotspot_audit_config.json")
RUNNER_REL = ".claude/skills/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py"
DEFAULT_RUNNER = str(Path.home() / RUNNER_REL)
DEFAULT_SKILLS_ROOT = str(Path.home() / ".claude/skills")


def identities(fs):
    return {_wf.identity(d) for d in fs}


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", help="read the active set from this file (tests)")
    ap.add_argument("--accepted", help="read the accept sidecar from this file (tests)")
    return ap.parse_args(argv)


def _run_wave():
    """Run the wave (it auto-suppresses via the in-repo accept.json); return out dir."""
    runner = os.environ.get("WAVE_RUNNER", DEFAULT_RUNNER)
    out = REPO / ".wave_out"
    cmd = [sys.executable, runner, "--repo", str(REPO), "--out-dir", str(out)]
    cmd += ["--skills-root", os.environ.get("SKILLS_ROOT", DEFAULT_SKILLS_ROOT)]
    cmd += ["--source-prefix", "scripts"]
    rev = os.environ.get("WAVE_REV")
    if not rev and WAVE_ANCHOR.exists():
        rev = WAVE_ANCHOR.read_text(encoding="utf-8").strip()
    if rev:
        cmd += ["--rev", rev]
    security_config = os.environ.get("SECURITY_CONFIG")
    if not security_config and SECURITY_CONFIG.exists():
        security_config = str(SECURITY_CONFIG)
    if security_config:
        cmd += ["--security-config", security_config]
    hotspot_config = os.environ.get("HOTSPOT_CONFIG")
    if not hotspot_config and HOTSPOT_CONFIG.exists():
        hotspot_config = str(HOTSPOT_CONFIG)
    if hotspot_config:
        cmd += ["--hotspot-config", hotspot_config]
    # Runner path may come from WAVE_RUNNER; shell stays disabled.
    subprocess.run(cmd, check=False)  # nosec B603: shell=False
    return out


def _emit(payload):
    print(json.dumps(payload, indent=2))


def _fail(payload):
    _emit(payload)
    return 1


def _converge(active, accepted_sidecar):
    """Option A verdict: pass iff active is empty AND no stale acceptances."""
    if active:
        return _fail({
            "status": "fail",
            "new_findings": sorted(map(list, identities(active))),
        })
    stale = list(accepted_sidecar.get("stale", []))
    if stale:
        return _fail({"status": "fail", "stale_acceptances": sorted(stale)})
    accepted = accepted_sidecar.get("accepted", [])
    _emit({"status": "pass", "accepted": len(accepted), "active": 0})
    return 0


def main(argv=None):
    args = _parse_args(argv)
    if args.snapshot:
        active = _load_json(args.snapshot)
        sidecar = _load_json(args.accepted) if args.accepted else {"stale": []}
    else:
        out = _run_wave()
        active = _load_json(out / "wave_findings.json")
        sidecar = _load_json(out / "wave_findings.accepted.json")
    return _converge(active, sidecar)


if __name__ == "__main__":
    sys.exit(main())
