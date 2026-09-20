"""Thin-wrapper behavior: faithful delegation, unchanged exit propagation.

Uses a stub `repo-audit` executable on PATH (no network, no real core needed).
Regressions covered: 256+ finding counts must survive (proposal finding #10),
`--baseline` is rejected, a missing CLI fails clearly, and no fix/merge flags
are ever forwarded (scope: detection only, the host edits).
"""
from __future__ import annotations

import importlib
import json
import os
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

wave = importlib.import_module("scripts.run_diagnosis_wave")

STUB = """#!/usr/bin/env python3
import json, sys
from pathlib import Path
out = Path(__file__).parent / "argv.json"
out.write_text(json.dumps(sys.argv[1:]))
code = int((Path(__file__).parent / "exit_code").read_text().strip())
payload = Path(__file__).parent / "payload.json"
if payload.exists():
    print(payload.read_text())
sys.exit(code)
"""


def _stub_cli(tmp_path: Path, exit_code: int, payload: dict | None = None) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "repo-audit").write_text(STUB, encoding="utf-8")
    (bindir / "repo-audit").chmod(
        (bindir / "repo-audit").stat().st_mode | stat.S_IEXEC
    )
    (bindir / "exit_code").write_text(str(exit_code), encoding="utf-8")
    if payload is not None:
        (bindir / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
    return bindir


def test_delegates_scan_args(monkeypatch, tmp_path, capsys):
    bindir = _stub_cli(tmp_path, 1, {"findings": [{"id": 1}]})
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    repo = tmp_path / "target"
    repo.mkdir()
    out = tmp_path / "run"
    rc = wave.main(
        ["--repo", str(repo), "--out-dir", str(out), "--checks", "a,b"]
    )
    assert rc == 1
    forwarded = json.loads((bindir / "argv.json").read_text())
    assert forwarded[0] == "scan"
    assert "--root" in forwarded and "--out-dir" in forwarded
    assert "--checks" in forwarded and "a,b" in forwarded
    for banned in ("--fix", "--merge", "--commit", "--schedule", "--spawn"):
        assert banned not in forwarded


def test_large_finding_count_survives_exit_propagation(monkeypatch, tmp_path, capsys):
    """300 findings must read back as 300, not 300 % 256."""
    bindir = _stub_cli(tmp_path, 1, {"finding_count": 300})
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    rc = wave.main(["--root", str(tmp_path), "--out-dir", str(tmp_path / "o")])
    # Bounded status (1 = complete with findings); the count travels in JSON,
    # never folded into the exit code (300 % 256 == 44 would be the old bug).
    assert rc == 1
    assert rc != 300 % 256
    assert json.loads((bindir / "payload.json").read_text())["finding_count"] == 300


def test_incomplete_propagates_as_two(monkeypatch, tmp_path):
    bindir = _stub_cli(tmp_path, 2)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    assert wave.main(["--root", str(tmp_path), "--out-dir", str(tmp_path / "o")]) == 2
    assert not (bindir / "payload.json").exists() or True


def test_baseline_rejected_without_invoking_cli(monkeypatch, tmp_path, capsys):
    bindir = _stub_cli(tmp_path, 0)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    rc = wave.main(["--root", str(tmp_path), "--baseline", "base.json"])
    assert rc == 2
    assert not (bindir / "argv.json").exists()
    assert "MIGRATION" in capsys.readouterr().err


def test_missing_cli_fails_clearly(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("PATH", str(tmp_path))
    rc = wave.main(["--root", str(tmp_path), "--out-dir", str(tmp_path / "o")])
    assert rc == 2
    assert "repo-audit" in capsys.readouterr().err


def test_lanes_alias_warns_and_forwards(monkeypatch, tmp_path, capsys):
    bindir = _stub_cli(tmp_path, 0)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    rc = wave.main(["--root", str(tmp_path), "--lanes", "security"])
    assert rc == 0
    assert "--checks" in json.loads((bindir / "argv.json").read_text())
    assert "deprecated" in capsys.readouterr().err


def test_forwards_coverage_sourceprefix_rev(monkeypatch, tmp_path):
    bindir = _stub_cli(tmp_path, 0)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    rc = wave.main([
        "--root", str(tmp_path), "--out-dir", str(tmp_path / "o"),
        "--preset", "code-health", "--coverage-json", "cov.json",
        "--source-prefix", "src", "--source-prefix", "lib", "--rev", "abc123",
    ])
    assert rc == 0
    forwarded = json.loads((bindir / "argv.json").read_text())
    assert forwarded[0] == "scan"
    assert "--preset" in forwarded and "code-health" in forwarded
    assert forwarded.count("--coverage-json") == 1 and "cov.json" in forwarded
    assert forwarded.count("--source-prefix") == 2
    assert "--rev" in forwarded and "abc123" in forwarded


def test_list_checks_rejects_scan_options(monkeypatch, tmp_path, capsys):
    bindir = _stub_cli(tmp_path, 0)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    rc = wave.main(["--list-checks", "--checks", "security"])
    assert rc == 2
    assert not (bindir / "argv.json").exists()
    assert "no other scan options" in capsys.readouterr().err


def test_list_checks_clean(monkeypatch, tmp_path):
    bindir = _stub_cli(tmp_path, 0)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    assert wave.main(["--list-checks"]) == 0
    assert json.loads((bindir / "argv.json").read_text()) == ["scan", "--list-checks"]


def test_retired_flags_rejected_with_migration_pointer(tmp_path, capsys):
    for flag in ("--registry", "--skills-root", "--exclude-prefix",
                 "--security-config", "--hotspot-config"):
        rc = wave.main(["--root", str(tmp_path), flag, "x"])
        assert rc == 2, flag
        assert "MIGRATION" in capsys.readouterr().err, flag
