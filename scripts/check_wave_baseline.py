#!/usr/bin/env python3
"""Convergence gate: diagnosis wave on this repo, equality-ratcheted against wave_baseline.json."""

import argparse, json, os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name("wave_baseline.json")


def identities(fs):
    return {tuple(sorted(d.items())) for d in fs}


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    ap.add_argument("--baseline")
    a = ap.parse_args(argv)
    if a.snapshot:
        current = _load_json(a.snapshot)
    else:
        runner = os.environ.get(
            "WAVE_RUNNER",
            str(Path.home() / ".claude/skills/repo-audit-refactor-optimize/scripts/run_diagnosis_wave.py"),
        )
        out = REPO / ".wave_out"
        subprocess.run(
            [sys.executable, runner, "--repo", str(REPO), "--out-dir", str(out),
             "--skills-root", os.environ.get("SKILLS_ROOT", str(Path.home() / ".claude/skills")),
             "--source-prefix", "scripts"], check=False
        )
        current = _load_json(out / "wave_findings.json")

    baseline = _load_json(a.baseline or BASELINE)
    cur, base = identities(current), identities(baseline)
    new, stale = cur - base, base - cur
    if new:
        print(json.dumps({"status": "fail", "new_findings": sorted(map(list, new))}, indent=2))
        return 1
    if stale:
        print(json.dumps({
            "status": "fail",
            "stale_baseline": sorted(map(list, stale)),
            "message": f"ratchet: remove them from {BASELINE.name} in the same commit",
        }, indent=2))
        return 1
    print(json.dumps({"status": "pass", "count": len(cur), "baseline": len(base)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
