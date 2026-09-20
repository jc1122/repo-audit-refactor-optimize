"""Installer behavior: same body on both harnesses, dest-scoped, honest plan.

No network: --skip-core for real installs, --dry-run for plan assertions.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "bootstrap" / "install.sh"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT.parent),
    )


def test_dry_run_creates_nothing(tmp_path):
    dest = tmp_path / "skills"
    before = list(tmp_path.iterdir())
    proc = _run("--dest", str(dest), "--dry-run", "--harness", "codex")
    assert proc.returncode == 0, proc.stderr
    assert list(tmp_path.iterdir()) == before
    assert "DRY:" in proc.stdout


def test_dry_run_shows_core_plan(tmp_path):
    proc = _run(
        "--dest", str(tmp_path / "s"), "--dry-run",
        "--core", "git+https://example.com/x@v1.0.0",
    )
    assert proc.returncode == 0, proc.stderr
    assert "pip install" in proc.stdout
    assert "git+https://example.com/x@v1.0.0" in proc.stdout


def test_unknown_harness_rejected(tmp_path):
    proc = _run("--dest", str(tmp_path / "s"), "--harness", "eclipse", "--dry-run")
    assert proc.returncode == 2


def _installed_files(dest: Path) -> list[Path]:
    root = dest / "repo-audit-refactor-optimize"
    return sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())


def test_real_install_same_body_both_harnesses(tmp_path):
    codex_dest = tmp_path / "codex-skills"
    claude_dest = tmp_path / "claude-skills"
    for dest, harness in ((codex_dest, "codex"), (claude_dest, "claude")):
        proc = _run("--dest", str(dest), "--harness", harness, "--skip-core")
        assert proc.returncode == 0, proc.stderr
    codex_files = _installed_files(codex_dest)
    claude_files = _installed_files(claude_dest)
    assert codex_files == claude_files
    assert Path("SKILL.md") in codex_files
    for ref in (
        "acceptance.md",
        "prioritization.md",
        "remediation-playbook.md",
        "verification.md",
        "MIGRATION.md",
    ):
        assert Path("references") / ref in codex_files
    # Byte-identical bodies across harnesses.
    for rel in codex_files:
        a = (codex_dest / "repo-audit-refactor-optimize" / rel).read_bytes()
        b = (claude_dest / "repo-audit-refactor-optimize" / rel).read_bytes()
        assert a == b, f"{rel} differs between harnesses"


def test_install_ships_no_tests_or_history(tmp_path):
    dest = tmp_path / "skills"
    proc = _run("--dest", str(dest), "--skip-core")
    assert proc.returncode == 0, proc.stderr
    names = [p.as_posix() for p in _installed_files(dest)]
    assert not any(n.startswith("tests/") for n in names)
    assert not any("superpowers" in n or "audits" in n for n in names)


def test_install_writes_only_under_dest(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    dest = work / "skills"
    sentinel = work / "sentinel.txt"
    sentinel.write_text("untouched", encoding="utf-8")
    proc = _run("--dest", str(dest), "--skip-core")
    assert proc.returncode == 0, proc.stderr
    leftovers = sorted(
        p.relative_to(work) for p in work.rglob("*") if p.is_file()
    )
    assert all(str(p).startswith("skills/") or p == Path("sentinel.txt") for p in leftovers), leftovers
    assert sentinel.read_text(encoding="utf-8") == "untouched"


HOSTILE = "out $(touch PWNED) 'quoted' `id`"


def test_hostile_dest_stays_literal_in_dry_run(tmp_path):
    dest = tmp_path / HOSTILE
    work = tmp_path / "cwd"
    work.mkdir()
    proc = _run("--dest", str(dest), "--core", "evil;touch PWNED2", "--dry-run",
                cwd=work)
    assert proc.returncode == 0, proc.stderr
    # Nothing created, nothing executed: both dirs stay as they were, and the
    # DRY plan quotes the hostile text (%q) instead of interpreting it.
    assert list(tmp_path.iterdir()) == [work]
    assert list(work.iterdir()) == []
    assert "touch\\ PWNED" in proc.stdout or "\\$(" in proc.stdout
    for stray in ("PWNED", "PWNED2"):
        assert not (work / stray).exists()
        assert not (tmp_path / stray).exists()


def test_hostile_dest_real_install_stays_literal(tmp_path):
    dest = tmp_path / HOSTILE
    proc = _run("--dest", str(dest), "--skip-core")
    assert proc.returncode == 0, proc.stderr
    # The skill lands under the literally-named directory; no sibling
    # execution artifacts (no PWNED file anywhere under tmp).
    assert (dest / "repo-audit-refactor-optimize" / "SKILL.md").is_file()
    assert list(tmp_path.rglob("PWNED*")) == []


def test_installed_scripts_verified_present(tmp_path):
    dest = tmp_path / "skills"
    proc = _run("--dest", str(dest), "--skip-core")
    assert proc.returncode == 0, proc.stderr
    scripts = dest / "repo-audit-refactor-optimize" / "scripts"
    for name in ("run_diagnosis_wave.py",):
        assert (scripts / name).is_file(), f"shipped script missing: {name}"


def test_core_probe_policy_list_checks_hard_doctor_soft(tmp_path, monkeypatch):
    """Missing optional tools must not fail the install.

    A stub core whose `scan --list-checks` passes but `doctor` fails must
    still install green with a doctor note on stderr. pip itself is faked
    (records argv, installs nothing) so no environment is touched.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # Python stub CLI written directly (no shell round-trip): runs under any
    # interpreter, both via kernel exec (shebang) and `bin/python script args`
    # mediation like the real install uses.
    stub_src = (
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "a = sys.argv[1:]\n"
        "if a[:2] == ['scan', '--list-checks']:\n"
        "    print(json.dumps({'checks': []}))\n"
        "elif a[:1] == ['doctor']:\n"
        "    print(json.dumps({'missing': 1}), file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "else:\n"
        "    sys.exit(2)\n"
    )
    (bindir / "repo-audit-stub.py").write_text(stub_src)
    (bindir / "repo-audit").write_text(stub_src)
    (bindir / "repo-audit").chmod(0o755)
    real_python = subprocess.run(
        ["bash", "-c", "command -v python3"], capture_output=True, text=True
    ).stdout.strip()
    shim = [
        "#!/usr/bin/env bash",
        # Fake environment provider: `-m venv DIR` builds a stub env whose
        # python is this shim itself (so `-m pip` stays intercepted) and
        # copies in the stub CLI. `-m pip` only records argv. Everything else
        # delegates to the real interpreter. No env touched, no network.
        "STUB=" + str(bindir / "repo-audit-stub.py"),
        "if [ \"$1 $2\" = \"-m venv\" ]; then",
        "  mkdir -p \"$3/bin\"",
        "  cp \"$0\" \"$3/bin/python\"",
        "  cp \"$STUB\" \"$3/bin/repo-audit\"",
        "  chmod +x \"$3/bin/repo-audit\"",
        "  exit 0",
        "fi",
        "if [ \"$1 $2\" = \"-m pip\" ]; then",
        "  echo \"FAKE-PIP $*\" >> \"" + str(bindir / "pip.log") + "\"",
        "  exit 0",
        "fi",
        "exec \"" + real_python + "\" \"$@\"",
    ]
    (bindir / "python3").write_text("\n".join(shim) + "\n")
    (bindir / "python3").chmod(0o755)
    import os
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    dest = tmp_path / "skills"
    proc = _run("--dest", str(dest), "--core", "stub-core-spec")
    assert proc.returncode == 0, proc.stderr
    assert (dest / "repo-audit-refactor-optimize" / "SKILL.md").is_file()
    pip_log = (bindir / "pip.log").read_text()
    assert "FAKE-PIP" in pip_log and "stub-core-spec" in pip_log
    assert "doctor" in proc.stderr
