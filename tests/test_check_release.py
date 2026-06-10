"""Tests for scripts/check_release.py — release gate checks."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# write_skill and write_manifest helpers (same pattern as test_check_skill_requirements.py)


def write_skill(root: Path, name: str, version: str | None = None) -> None:
    """Create a minimal SKILL.md with frontmatter under root/name/."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = f"name: {name}"
    if version is not None:
        frontmatter += f"\nversion: {version}"
    (skill_dir / "SKILL.md").write_text(
        f"---\n{frontmatter}\ndescription: test skill\n---\n",
        encoding="utf-8",
    )


def write_manifest(path: Path, payload: dict) -> None:
    """Write a JSON manifest."""
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_changelog(root: Path, version: str) -> None:
    """Write a CHANGELOG.md with a ## <version> heading."""
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {version}\n\n- Some changes\n\n## 0.0.1\n\n- Initial\n",
        encoding="utf-8",
    )


# ── test cases ──────────────────────────────────────────────────────────────


def test_pass_case_exits_zero(tmp_path: Path, capsys):
    """All checks pass: valid semver, matching CHANGELOG, valid manifest."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # SKILL.md with valid semver
    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 1.2.3\ndescription: test\n---\n",
        encoding="utf-8",
    )
    # CHANGELOG.md with matching heading
    write_changelog(repo, "1.2.3")
    # manifest with skills + lanes
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    write_manifest(
        scripts_dir / "skill_bootstrap_manifest.json",
        {"version": 1, "skills": {"s": {}}, "lanes": {"l": {}}},
    )

    mod = importlib.import_module("scripts.check_release")
    rc = mod.main(["--root", str(repo)])
    assert rc == 0
    stdout = capsys.readouterr().out
    result = json.loads(stdout)
    assert result["status"] == "pass"


def test_missing_changelog_heading_exits_one(tmp_path: Path, capsys):
    """CHANGELOG.md exists but lacks a ## <version> heading for the current version."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 1.2.3\ndescription: test\n---\n",
        encoding="utf-8",
    )
    # CHANGELOG.md exists but does NOT contain ## 1.2.3
    (repo / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.0.1\n\n- Old version\n",
        encoding="utf-8",
    )
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    write_manifest(
        scripts_dir / "skill_bootstrap_manifest.json",
        {"version": 1, "skills": {"s": {}}, "lanes": {"l": {}}},
    )

    mod = importlib.import_module("scripts.check_release")
    rc = mod.main(["--root", str(repo)])
    assert rc == 1
    stdout = capsys.readouterr().out
    result = json.loads(stdout)
    assert result["status"] == "fail"
    assert any("CHANGELOG" in d for d in result["defects"])
    assert any("1.2.3" in d for d in result["defects"])


def test_non_semver_frontmatter_exits_one(tmp_path: Path, capsys):
    """Version in SKILL.md is not valid semver → exit 1."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: not-a-version\ndescription: test\n---\n",
        encoding="utf-8",
    )
    (repo / "CHANGELOG.md").write_text(
        "# Changelog\n\n## not-a-version\n\n- stuff\n",
        encoding="utf-8",
    )
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    write_manifest(
        scripts_dir / "skill_bootstrap_manifest.json",
        {"version": 1, "skills": {"s": {}}, "lanes": {"l": {}}},
    )

    mod = importlib.import_module("scripts.check_release")
    rc = mod.main(["--root", str(repo)])
    assert rc == 1
    stdout = capsys.readouterr().out
    result = json.loads(stdout)
    assert result["status"] == "fail"
    assert any("version" in d.lower() for d in result["defects"])


def test_missing_manifest_file_exits_one(tmp_path: Path, capsys):
    """Manifest file does not exist → exit 1."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 1.2.3\ndescription: test\n---\n",
        encoding="utf-8",
    )
    write_changelog(repo, "1.2.3")
    # No scripts/ directory at all — manifest is missing

    mod = importlib.import_module("scripts.check_release")
    rc = mod.main(["--root", str(repo)])
    assert rc == 1
    stdout = capsys.readouterr().out
    result = json.loads(stdout)
    assert result["status"] == "fail"
    assert any("manifest" in d.lower() for d in result["defects"])
