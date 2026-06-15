"""Every runnable entry point must work when run as a direct script.

Regression guard: a script that imports the ``scripts`` package at top level
(``from scripts import ...``) AND is runnable (``if __name__ == "__main__"``)
must insert the repo root onto ``sys.path`` before that import. Otherwise
``python3 scripts/<name>.py`` — the exact form the SKILL.md docs imply —
crashes with ``ModuleNotFoundError: No module named 'scripts'`` even though
``python3 -m scripts.<name>`` works. ``mprr_run.py`` carries the canonical
3-line bootstrap; this test holds the rest of the family to the same bar.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def _runnable_package_importers() -> list[str]:
    """Scripts that both import the `scripts` package and are runnable."""
    out: list[str] = []
    for p in sorted(SCRIPTS.glob("*.py")):
        text = p.read_text(encoding="utf-8")
        imports_pkg = "from scripts import" in text or "from scripts." in text
        runnable = '__name__ == "__main__"' in text or "__name__ == '__main__'" in text
        if imports_pkg and runnable:
            out.append(p.name)
    return out


@pytest.mark.parametrize("script", _runnable_package_importers())
def test_direct_script_invocation_does_not_crash(script: str) -> None:
    # Run from a neutral cwd so only an explicit sys.path bootstrap (not an
    # accidental cwd-on-path) can make the `scripts` package importable.
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT.parent),
    )
    assert "ModuleNotFoundError" not in proc.stderr, (
        f"{script} crashed as a direct script:\n{proc.stderr}"
    )
    assert proc.returncode == 0, f"{script} --help exited {proc.returncode}:\n{proc.stderr}"
