from __future__ import annotations

import sys
import pytest
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


def test_skill_entry_marks_usable_without_warnings_when_version_satisfies_minimum() -> None:
    usable = {
        "demo-skill": {
            "root_kind": "extra",
            "skill_path": "/tmp/demo-skill/SKILL.md",
            "version": "2.0.0",
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

    assert entry["state"] == "usable_now"
    assert "warnings" not in entry
    assert entry["found_version"] == "2.0.0"


def test_skill_entry_marks_advisory_only_when_only_advisory_discovery() -> None:
    advisory = {
        "demo-skill": {
            "root_kind": "extra",
            "skill_path": "/tmp/demo-skill/SKILL.md",
        }
    }

    entry = probe._skill_entry(
        "demo-skill",
        {
            "priority": "preferred",
            "source_type": "public",
            "install_source": {"method": "local"},
            "manual_fallback": "Install manually.",
            "restart_required_if_installed": False,
        },
        usable_skills={},
        advisory_skills=advisory,
    )

    assert entry["state"] == "advisory_only"
    assert entry["root_kind"] == "extra"
    assert entry["skill_path"] == "/tmp/demo-skill/SKILL.md"


def test_skill_entry_marks_installable_when_public_skill_is_installable() -> None:
    entry = probe._skill_entry(
        "demo-skill",
        {
            "priority": "preferred",
            "source_type": "public",
            "install_source": {"method": "skills_cli", "package": "demo"},
            "manual_fallback": "Install manually.",
            "restart_required_if_installed": False,
        },
        usable_skills={},
        advisory_skills={},
    )

    assert entry["state"] == "installable_now"
    assert entry["post_install_state"] == "available_next_run"


def test_skill_entry_marks_manual_when_not_discoverable_or_installable() -> None:
    entry = probe._skill_entry(
        "demo-skill",
        {
            "priority": "preferred",
            "source_type": "local",
            "install_source": {},
            "manual_fallback": "Install manually.",
            "restart_required_if_installed": False,
        },
        usable_skills={},
        advisory_skills={},
    )

    assert entry["state"] == "manual_only"


def test_skill_entry_required_fields_are_enforced() -> None:
    with pytest.raises(ValueError, match=r"Skill 'demo-skill' is missing required field"):
        probe._skill_entry(
            "demo-skill",
            {
                "priority": "preferred",
                "source_type": "public",
                "manual_fallback": "Install manually.",
                "min_version": "1.0.0",
            },
            usable_skills={},
            advisory_skills={},
        )


_ALWAYS_CFG = {
    "priority": "preferred",
    "source_type": "user-local",
    "manual_fallback": "manual",
    "restart_required_if_installed": True,
    "always_available": True,
}


def test_always_available_resolves_usable_without_filesystem() -> None:
    entry = probe._skill_entry("verification-before-completion", _ALWAYS_CFG,
                               usable_skills={}, advisory_skills={})
    assert entry["state"] == "usable_now"
    assert entry["root_kind"] == "harness"


def test_always_available_skipped_when_flag_absent_is_manual() -> None:
    cfg = {k: v for k, v in _ALWAYS_CFG.items() if k != "always_available"}
    entry = probe._skill_entry("some-leaf", cfg, usable_skills={}, advisory_skills={})
    assert entry["state"] == "manual_only"
