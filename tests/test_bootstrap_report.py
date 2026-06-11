from __future__ import annotations

import json
import importlib
from pathlib import Path

import pytest


boot = importlib.import_module("scripts._bootstrap_report")


def write_skill(root: Path, name: str) -> None:
    """Create a minimal skill with frontmatter."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\nversion: 1.0.0\ndescription: demo skill\n---\n",
        encoding="utf-8",
    )


def write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _minimal_manifest() -> dict:
    return {
        "skills": {
            "demo-skill": {
                "priority": "preferred",
                "source_type": "public",
                "install_source": {
                    "method": "skills_cli",
                    "package": "acme/demo-skill",
                },
                "manual_fallback": "Install demo manually.",
                "restart_required_if_installed": False,
            }
        },
        "lanes": {
            "demo-lane": {
                "lane_type": "test",
                "preferred": ["demo-skill"],
                "manual_fallback": "Use fallback skill.",
                "always": True,
            }
        },
    }


def test_build_bootstrap_report_happy_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("def test_app(): pass\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    agents_skills = tmp_path / ".agents" / "skills"
    write_skill(agents_skills, "demo-skill")

    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _minimal_manifest())

    report = boot.build_bootstrap_report(
        repo_root=repo,
        manifest_path=manifest_path,
        out_dir=tmp_path / "out",
        env={"HOME": str(tmp_path)},
    )

    assert "python" in report["repo_profile"]["languages"]
    lane = report["lanes"]["demo-lane"]
    assert lane["state"] == "full"
    assert lane["selected_skills"] == ["demo-skill"]
    assert report["summary"]["stop_before_discovery"] is False

    boot.write_bootstrap_outputs(report, tmp_path / "out")
    bootstrap_dir = tmp_path / "out" / "bootstrap"
    assert (bootstrap_dir / "bootstrap_report.json").exists()
    assert (bootstrap_dir / "bootstrap_report.md").exists()
    assert (bootstrap_dir / "install_plan.md").exists()


def test_build_bootstrap_report_missing_repo_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, _minimal_manifest())

    with pytest.raises(ValueError, match="Repository root does not exist"):
        boot.build_bootstrap_report(
            repo_root=tmp_path / "missing",
            manifest_path=manifest_path,
            out_dir=tmp_path / "out",
            env={"HOME": str(tmp_path)},
        )
