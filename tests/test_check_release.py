"""Release gate behavior: passes on this repo, fails honestly on drift."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

cr = importlib.import_module("scripts.check_release")


def test_pass_on_real_repo(capsys):
    assert cr.main(["--root", str(REPO_ROOT)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


def _skeleton(root: Path, skill_head: str) -> None:
    (root / "SKILL.md").write_text(skill_head, encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0\n", encoding="utf-8")
    (root / "references").mkdir()
    for ref in cr.REQUIRED_REFERENCES:
        (root / "references" / ref).write_text("x\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "run_diagnosis_wave.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
    (scripts / "repo-audit").write_text('#!/bin/sh\n', encoding="utf-8")
    bootstrap = root / "bootstrap"
    bootstrap.mkdir()
    (bootstrap / "install.sh").write_text(
        'SKILL_VERSION="1.0.0"\nrepo-audit-skills@v1.0.0\n'
        '"$PYTHON_BIN" -m venv\n"$VENV/bin/python" -m pip install\n',
        encoding="utf-8",
    )


GOOD_SKILL = (
    "---\nname: repo-audit-refactor-optimize\n"
    "description: test skill\n"
    "metadata:\n  version: 1.0.0\n  requires: \"repo-audit-checks >= 1.0.0\"\n---\n"
    "body with \"$SKILL_DIR/scripts/repo-audit\" doctor,\n"
    "\"$SKILL_DIR/scripts/repo-audit\" scan and\n"
    "\"$SKILL_DIR/scripts/repo-audit\" compare examples\n"
)


def test_pass_on_skeleton_repo(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _skeleton(repo, GOOD_SKILL)
    assert cr.main(["--root", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


def test_top_level_version_rejected(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _skeleton(
        repo,
        "---\nname: repo-audit-refactor-optimize\ndescription: t\nversion: 1.0.0\n"
        "metadata:\n  version: 1.0.0\n---\nbody\n",
    )
    assert cr.main(["--root", str(repo)]) == 1
    out = capsys.readouterr().out
    assert "metadata.version" in out


def test_retired_machinery_rejected(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _skeleton(repo, GOOD_SKILL)
    (repo / "scripts" / "mprr_run.py").write_text("x\n", encoding="utf-8")
    assert cr.main(["--root", str(repo)]) == 1
    assert "mprr_run.py" in capsys.readouterr().out


def test_installer_pin_drift_rejected(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _skeleton(repo, GOOD_SKILL)
    (repo / "bootstrap" / "install.sh").write_text(
        'SKILL_VERSION="0.12.1"\nrepo-audit-skills@v0.8.0\n', encoding="utf-8"
    )
    assert cr.main(["--root", str(repo)]) == 1
    assert "drift" in capsys.readouterr().out


def test_bad_requires_rejected(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _skeleton(repo, GOOD_SKILL.replace("repo-audit-checks >= 1.0.0", "other-pkg"))
    assert cr.main(["--root", str(repo)]) == 1
    assert "requires" in capsys.readouterr().out


def test_deleted_config_reappearance_rejected(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _skeleton(repo, GOOD_SKILL)
    (repo / "scripts" / "toolchain_pins.json").write_text("{}\n", encoding="utf-8")
    assert cr.main(["--root", str(repo)]) == 1
    assert "toolchain_pins.json" in capsys.readouterr().out
