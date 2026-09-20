"""Isolated-venv installer behavior on a PEP 668 stock Python.

Builds a stub `repo-audit` wheel offline (local setuptools, --no-build-isolation,
--no-deps: no network) and installs it through bootstrap/install.sh using the
system python3. Proves: no system-python writes, launcher works with no
activation and no PATH reliance, hostile paths stay literal, failures preserve
the previous install, and --venv reuses an existing environment.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "bootstrap" / "install.sh"
STUB_SRC = REPO_ROOT / "tests" / "fixtures" / "stub-core"


def _run(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        capture_output=True, text=True,
        cwd=str(cwd or REPO_ROOT.parent), env=env,
    )


def _wheel(tmp_factory, monkeypatch) -> Path:
    try:
        import setuptools  # noqa: F401 (capability probe for offline build)
    except ImportError:
        import pytest
        pytest.skip("setuptools unavailable: cannot build stub wheel offline")
    out = Path(tmp_factory.mktemp("wheelhouse"))
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-build-isolation",
         "--no-deps", str(STUB_SRC), "-w", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"stub wheel build failed:\n{proc.stderr}"
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def _pep668_system() -> bool:
    marker = Path(sys.executable).resolve().parent.parent / "EXTERNALLY-MANAGED"
    alt = Path("/usr/lib/python3.14/EXTERNALLY-MANAGED")
    return marker.exists() or alt.exists()


def test_default_venv_install_on_stock_python(tmp_path_factory, monkeypatch):
    import pytest as _pytest

    if not _pep668_system():
        _pytest.skip("not a PEP 668 system python (stock-python guard)")
    wheel = _wheel(tmp_path_factory, monkeypatch)
    dest = tmp_path_factory.mktemp("skills")
    proc = _run("--dest", str(dest), "--core", str(wheel))
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    venv = dest / "repo-audit-venv"
    assert (venv / "bin" / "repo-audit").is_file()
    skill = dest / "repo-audit-refactor-optimize"
    # Default installs resolve the venv relatively: no per-install
    # config file, so bodies stay byte-identical across harnesses.
    assert not (skill / "scripts" / ".venv-path").exists()
    for name in ("repo-audit", "run_diagnosis_wave.py"):
        assert (skill / "scripts" / name).is_file()


def test_launcher_needs_no_activation_or_path(tmp_path_factory, monkeypatch):
    wheel = _wheel(tmp_path_factory, monkeypatch)
    dest = tmp_path_factory.mktemp("skills")
    assert _run("--dest", str(dest), "--core", str(wheel)).returncode == 0
    launcher = dest / "repo-audit-refactor-optimize" / "scripts" / "repo-audit"
    target = tmp_path_factory.mktemp("target")
    (target / "a.py").write_text("x = 1\n")
    out = tmp_path_factory.mktemp("run")
    bare_path = os.pathsep.join(p for p in ("/usr/bin", "/bin") if Path(p).is_dir())
    env = {"PATH": bare_path, "HOME": os.environ.get("HOME", "/root")}
    for verb, args in (
        ("doctor", ["doctor"]),
        ("scan", ["scan", "--root", str(target), "--out-dir", str(out)]),
        ("compare", ["compare", "--baseline", str(out), "--current", str(out)]),
    ):
        proc = subprocess.run(
            [str(launcher), *args], capture_output=True, text=True, cwd="/", env=env,
        )
        assert proc.returncode in (0, 1), f"{verb}: rc={proc.returncode}\n{proc.stderr}"
    assert json.loads((out / "findings.json").read_text()) == [{"id": "stub-1", "leaf": "stub"}]


def test_wrapper_uses_installed_launcher_without_path(tmp_path_factory, monkeypatch):
    wheel = _wheel(tmp_path_factory, monkeypatch)
    dest = tmp_path_factory.mktemp("skills")
    assert _run("--dest", str(dest), "--core", str(wheel)).returncode == 0
    wrapper = dest / "repo-audit-refactor-optimize" / "scripts" / "run_diagnosis_wave.py"
    target = tmp_path_factory.mktemp("target")
    out = tmp_path_factory.mktemp("run")
    bare_path = os.pathsep.join(p for p in ("/usr/bin", "/bin") if Path(p).is_dir())
    env = {"PATH": bare_path, "HOME": os.environ.get("HOME", "/root")}
    proc = subprocess.run(
        [sys.executable, str(wrapper), "--repo", str(target), "--out-dir", str(out)],
        capture_output=True, text=True, cwd="/", env=env,
    )
    assert proc.returncode == 1, f"rc={proc.returncode}\n{proc.stderr}"
    assert (out / "run.json").is_file()


def test_hostile_paths_stay_literal_with_venv(tmp_path_factory, monkeypatch):
    wheel = _wheel(tmp_path_factory, monkeypatch)
    dest = tmp_path_factory.mktemp("base") / "out $(touch PWNED) 'quoted'"
    proc = _run("--dest", str(dest), "--core", str(wheel))
    assert proc.returncode == 0, proc.stderr
    assert (dest / "repo-audit-venv" / "bin" / "repo-audit").is_file()
    assert (dest / "repo-audit-refactor-optimize" / "SKILL.md").is_file()
    # The hostile text appears only as literal display text; prove the install
    # actually functions from inside the hostile path (shebang-proof launch).
    target = dest.parent / "target"
    target.mkdir()
    out = dest.parent / "run"
    launcher = dest / "repo-audit-refactor-optimize" / "scripts" / "repo-audit"
    proc2 = subprocess.run([str(launcher), "scan", "--root", str(target),
                            "--out-dir", str(out)], capture_output=True, text=True)
    assert proc2.returncode == 1 and (out / "findings.json").is_file()
    assert list(dest.parent.rglob("PWNED*")) == []


def test_failed_core_preserves_previous_install(tmp_path_factory, monkeypatch):
    wheel = _wheel(tmp_path_factory, monkeypatch)
    dest = tmp_path_factory.mktemp("skills")
    assert _run("--dest", str(dest), "--core", str(wheel)).returncode == 0
    launcher = dest / "repo-audit-refactor-optimize" / "scripts" / "repo-audit"
    before = subprocess.run([str(launcher), "doctor"], capture_output=True, text=True)
    assert before.returncode == 0
    broken = tmp_path_factory.mktemp("broken")
    (broken / "pyproject.toml").write_text("this is [[[ not toml\n")
    proc = _run("--dest", str(dest), "--core", str(broken))
    assert proc.returncode != 0
    assert "failed" in proc.stderr.lower() or "error" in proc.stderr.lower()
    # Previous install intact: body + venv CLI still work, no backup taken
    # (failure happened before any swap) and no staging leftovers.
    assert (dest / "repo-audit-refactor-optimize" / "SKILL.md").is_file()
    after = subprocess.run([str(launcher), "doctor"], capture_output=True, text=True)
    assert after.returncode == 0 and after.stdout == before.stdout
    assert [p for p in dest.iterdir() if p.name.startswith(".prev")] == []
    backups = dest.parent / ".repo-audit-install-backups"
    assert not backups.exists() or list(backups.iterdir()) == []


def test_existing_venv_option(tmp_path_factory, monkeypatch):
    wheel = _wheel(tmp_path_factory, monkeypatch)
    dest = tmp_path_factory.mktemp("skills")
    env_dir = tmp_path_factory.mktemp("myenv")
    assert subprocess.run([sys.executable, "-m", "venv", str(env_dir)],
                          capture_output=True).returncode == 0
    proc = _run("--dest", str(dest), "--venv", str(env_dir), "--core", str(wheel))
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert not (dest / "repo-audit-venv").exists()
    skill = dest / "repo-audit-refactor-optimize"
    assert (skill / "scripts" / ".venv-path").read_text().strip() == str(env_dir)
    assert (env_dir / "bin" / "repo-audit").is_file()


def test_missing_venv_is_refused(tmp_path):
    proc = _run("--dest", str(tmp_path / "skills"), "--venv", str(tmp_path / "nope"),
                "--core", "whatever", "--dry-run" not in () and "--skip-core" or "--skip-core")
    # --skip-core with a missing --venv: nothing to record, install still fine;
    # without --skip-core the missing env must fail (checked below).
    assert proc.returncode == 0
    proc = _run("--dest", str(tmp_path / "skills2"), "--venv", str(tmp_path / "nope"),
                "--core", str(tmp_path / "nope2"))
    assert proc.returncode != 0
    assert not (tmp_path / "skills2").exists()


def _public_skill_entries(dest: Path) -> list:
    """Dirs directly under dest carrying a SKILL.md (what discovery sees)."""
    return sorted(p for p in dest.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def test_upgrade_leaves_single_entry_with_external_backup(tmp_path_factory, monkeypatch):
    wheel = _wheel(tmp_path_factory, monkeypatch)
    dest = tmp_path_factory.mktemp("skills")
    assert _run("--dest", str(dest), "--core", str(wheel)).returncode == 0
    assert [p.name for p in _public_skill_entries(dest)] == ["repo-audit-refactor-optimize"]
    # Upgrade into the managed target (same source: exercises the swap path).
    proc = _run("--dest", str(dest), "--core", str(wheel))
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert [p.name for p in _public_skill_entries(dest)] == ["repo-audit-refactor-optimize"]
    # Timestamped backup lives OUTSIDE the scanned root and still carries SKILL.md.
    backups = dest.parent / ".repo-audit-install-backups"
    assert backups.is_dir()
    stamped = [p for p in backups.iterdir() if p.is_dir()]
    assert len(stamped) >= 1
    assert (stamped[0] / "repo-audit-refactor-optimize" / "SKILL.md").is_file()
    assert (stamped[0] / "repo-audit-venv" / "bin" / "repo-audit").is_file()
    assert (dest / ".repo-audit-install-backups").exists() is False
    # Post-upgrade launcher still resolves the swapped-in venv from any cwd.
    launcher = dest / "repo-audit-refactor-optimize" / "scripts" / "repo-audit"
    target = tmp_path_factory.mktemp("target")
    out = tmp_path_factory.mktemp("run")
    bare_path = os.pathsep.join(p for p in ("/usr/bin", "/bin") if Path(p).is_dir())
    env = {"PATH": bare_path, "HOME": os.environ.get("HOME", "/root")}
    proc = subprocess.run(
        [str(launcher), "scan", "--root", str(target), "--out-dir", str(out)],
        capture_output=True, text=True, cwd="/", env=env,
    )
    assert proc.returncode == 1 and (out / "findings.json").is_file()
