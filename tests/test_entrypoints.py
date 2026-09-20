"""Every shipped script must work when run as a direct script.

Regression guard: `python3 scripts/<name>.py` (the form the docs imply) must
not crash with ModuleNotFoundError even though `python3 -m scripts.<name>`
also works. Run from a neutral cwd so only the script's own directory layout
— not an accidental cwd-on-path — can satisfy imports.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

ENTRY_POINTS = (
    "run_diagnosis_wave.py",
    "check_release.py",
)


def test_shipped_scripts_match_entry_points():
    # _accept.py is a library module, not an entry point.
    runnable = sorted(
        p.name
        for p in SCRIPTS.glob("*.py")
        if '__name__ == "__main__"' in p.read_text(encoding="utf-8")
    )
    assert sorted(ENTRY_POINTS) == runnable, f"entry-point drift: {runnable}"


def test_direct_script_invocation_does_not_crash():
    for script in ENTRY_POINTS:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / script), "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT.parent),
        )
        assert "ModuleNotFoundError" not in proc.stderr, (
            f"{script} crashed as a direct script:\n{proc.stderr}"
        )
        assert proc.returncode == 0, (
            f"{script} --help exited {proc.returncode}:\n{proc.stderr}"
        )
