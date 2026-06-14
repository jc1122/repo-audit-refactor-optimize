#!/usr/bin/env python3
"""Convergence gate: diagnosis wave on this repo.

Equality-ratcheted against `wave_baseline.json`.
"""

import argparse
import importlib
import json
import os
import subprocess  # nosec B404: local trusted wave runner
import sys
from pathlib import Path

_wf = importlib.import_module("scripts._wave_findings" if __package__ else "_wave_findings")

REPO = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name("wave_baseline.json")
WAVE_ANCHOR = Path(__file__).with_name("wave_anchor.txt")
SECURITY_CONFIG = Path(__file__).with_name("security_audit_config.json")
HOTSPOT_CONFIG = Path(__file__).with_name("hotspot_audit_config.json")
RUNNER_REL = ".claude/skills/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py"
DEFAULT_RUNNER = str(Path.home() / RUNNER_REL)
DEFAULT_SKILLS_ROOT = str(Path.home() / ".claude/skills")


# wave_timings.json contains non-deterministic timing telemetry.
# It is intentionally excluded from convergence/baseline byte comparison.
_TIMINGS_FILE = "wave_timings.json"


def identities(fs):
    return {_wf.identity(d) for d in fs}


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_findings(out_dir: Path):
    """Load wave findings for comparison, excluding timing telemetry.

    wave_timings.json is produced by the wave runner alongside
    wave_findings.json but contains non-deterministic timing data
    that varies across runs. It is intentionally excluded from
    the convergence ratchet — only wave_findings.json is compared
    against wave_baseline.json.
    """
    return _load_json(out_dir / "wave_findings.json")


def _parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    ap.add_argument("--baseline")
    return ap.parse_args(argv)


def _run_wave():
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
    return _load_findings(out)


def _emit(payload):
    print(json.dumps(payload, indent=2))


def _fail(payload):
    _emit(payload)
    return 1


def _stale_payload(stale):
    return {
        "status": "fail",
        "stale_baseline": sorted(map(list, stale)),
        "message": f"ratchet: remove them from {BASELINE.name} in the same commit",
    }


def _compare(current, baseline):
    cur, base = identities(current), identities(baseline)
    new, stale = cur - base, base - cur
    if new:
        return _fail({"status": "fail", "new_findings": sorted(map(list, new))})
    if stale:
        return _fail(_stale_payload(stale))
    _emit({"status": "pass", "count": len(cur), "baseline": len(base)})
    return 0


def main(argv=None):
    args = _parse_args(argv)
    current = _load_json(args.snapshot) if args.snapshot else _run_wave()
    baseline = _load_json(args.baseline or BASELINE)
    return _compare(current, baseline)


if __name__ == "__main__":
    sys.exit(main())
