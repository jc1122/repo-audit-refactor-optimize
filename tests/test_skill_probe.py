from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import _skill_probe as probe


def test_discover_skills_parses_name_version_and_paths(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill_dir = root / "demo-skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: demo-skill\nversion: 1.2.3\ndescription: demo\n---\n",
        encoding="utf-8",
    )

    discovered = probe._discover_skills([{"kind": "extra", "path": str(root)}])

    assert "demo-skill" in discovered
    entry = discovered["demo-skill"]
    assert entry["version"] == "1.2.3"
    assert entry["root_kind"] == "extra"
    assert entry["root_path"] == str(root)
    assert entry["skill_path"] == str(skill_file)


def test_skill_entry_marks_stale_install_when_version_below_minimum() -> None:
    usable = {
        "demo-skill": {
            "root_kind": "extra",
            "skill_path": "/tmp/demo-skill/SKILL.md",
            "version": "1.0.0",
        }
    }

    entry = probe._skill_entry(
        "demo-skill",
        {
            "priority": "preferred",
            "source_type": "local",
            "install_source": {},
            "manual_fallback": "Install manually.",
            "restart_required_if_installed": False,
            "min_version": "2.0.0",
        },
        usable_skills=usable,
        advisory_skills={},
    )

    assert entry["state"] == "stale_installed"
    assert entry["found_version"] == "1.0.0"
    assert any(
        "1.0.0" in warning and "2.0.0" in warning for warning in entry.get("warnings", [])
    )
