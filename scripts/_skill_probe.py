from __future__ import annotations

import os
from pathlib import Path
from typing import Any


_REQUIRED_SKILL_FIELDS = frozenset(
    {"priority", "source_type", "manual_fallback", "restart_required_if_installed"}
)


def _parse_version(v: str | None) -> tuple[int, int, int]:
    """Parse a semver-like string into a (major, minor, patch) tuple.

    Only the first three dot-separated integer parts are considered.
    Any failure (None, empty, non-numeric, etc.) returns (0, 0, 0).
    """
    if v is None:
        return (0, 0, 0)
    try:
        parts = v.split(".")
        nums: list[int] = []
        for part in parts[:3]:
            nums.append(int(part))
        while len(nums) < 3:
            nums.append(0)
        return (nums[0], nums[1], nums[2])
    except (ValueError, TypeError):
        return (0, 0, 0)


def _extract_skill_meta(skill_path: Path) -> tuple[str | None, str | None]:
    """Return (name, version) from the first 2048 bytes / 20 lines of a SKILL.md."""
    try:
        with open(skill_path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(2048)
    except OSError:
        return None, None
    name = None
    version = None
    for line in head.splitlines()[:20]:
        if line.startswith("name:") and name is None:
            name = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("version:") and version is None:
            version = line.split(":", 1)[1].strip().strip('"')
    return name, version


def _extract_skill_name(skill_path: Path) -> str | None:
    """Thin backward-compatible wrapper around ``_extract_skill_meta``."""
    name, _version = _extract_skill_meta(skill_path)
    return name


def _build_skill_entry_base(
    skill_name: str, skill_config: dict[str, Any]
) -> dict[str, Any]:
    """Build the common fields present in every skill report entry."""
    return {
        "name": skill_name,
        "priority": skill_config["priority"],
        "source_type": skill_config["source_type"],
        "install_source": skill_config.get("install_source"),
        "manual_fallback": skill_config["manual_fallback"],
        "restart_required_if_installed": skill_config[
            "restart_required_if_installed"
        ],
    }


def _validate_skill_entry_fields(
    skill_name: str, skill_config: dict[str, Any]
) -> None:
    for field in _REQUIRED_SKILL_FIELDS:
        if field not in skill_config:
            raise ValueError(
                f"Skill '{skill_name}' is missing required field '{field}'."
            )


def _apply_installable_or_manual_state(entry: dict[str, Any]) -> dict[str, Any]:
    if _install_command_for_skill(entry):
        return {
            **entry,
            "state": "installable_now",
            "post_install_state": "available_next_run",
        }
    return {**entry, "state": "manual_only"}


def _apply_advisory_state(
    entry: dict[str, Any], advisory: dict[str, Any]
) -> dict[str, Any]:
    return {
        **entry,
        "state": "advisory_only",
        "root_kind": advisory["root_kind"],
        "skill_path": advisory["skill_path"],
    }


def _evaluate_installed_skill(
    skill_name: str,
    skill_config: dict[str, Any],
    discovered: dict[str, Any],
) -> dict[str, Any]:
    min_version_str = skill_config.get("min_version")
    discovered_version_str = discovered.get("version")
    state = "usable_now"
    entry_warnings: list[str] = []

    if min_version_str is not None:
        min_ver = _parse_version(min_version_str)
        disc_ver = _parse_version(discovered_version_str)
        if disc_ver < min_ver:
            state = "stale_installed"
            found = discovered_version_str or "unknown"
            entry_warnings.append(
                f"Skill {skill_name} found at {found} < required "
                f"{min_version_str}; treated as stale_installed."
            )

    entry = {
        "state": state,
        "root_kind": discovered["root_kind"],
        "skill_path": discovered["skill_path"],
    }
    if min_version_str is not None:
        entry["min_version"] = min_version_str
        entry["found_version"] = discovered_version_str or "unknown"
    if entry_warnings:
        entry["warnings"] = entry_warnings
    return entry


def _scan_skill_subdir(
    sub_path: Path,
    root: dict[str, str],
    root_path: Path,
    discovered: dict[str, dict[str, Any]],
) -> None:
    """Scan one level deeper for ``<root>/<subdir>/<skill>/SKILL.md`` layouts."""
    try:
        sub_entries = sorted(os.scandir(sub_path), key=lambda e: e.name)
    except OSError:
        return
    for sub_entry in sub_entries:
        if not sub_entry.is_dir(follow_symlinks=True):
            continue
        nested = sub_path / sub_entry.name / "SKILL.md"
        if nested.exists():
            _register_skill(nested, root, root_path, discovered)


def _scan_skill_root(
    root: dict[str, str],
    discovered: dict[str, dict[str, Any]],
) -> None:
    """Scan one skill root directory and register all discovered SKILL.md files."""
    root_path = Path(root["path"])
    if not root_path.is_dir():
        return
    try:
        entries = sorted(os.scandir(root_path), key=lambda e: e.name)
    except OSError:
        return
    for entry in entries:
        if not entry.is_dir(follow_symlinks=True):
            continue
        skill_file = root_path / entry.name / "SKILL.md"
        if skill_file.exists():
            _register_skill(skill_file, root, root_path, discovered)
        else:
            # Support <root>/<subdir>/<skill>/SKILL.md (e.g. extra roots).
            _scan_skill_subdir(root_path / entry.name, root, root_path, discovered)


def _discover_skills(roots: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    for root in roots:
        _scan_skill_root(root, discovered)
    return discovered


def _register_skill(
    skill_file: Path,
    root: dict[str, str],
    root_path: Path,
    discovered: dict[str, dict[str, Any]],
) -> None:
    skill_name, version = _extract_skill_meta(skill_file)
    if skill_name and skill_name not in discovered:
        entry: dict[str, Any] = {
            "root_kind": root["kind"],
            "root_path": str(root_path),
            "skill_path": str(skill_file),
        }
        if version is not None:
            entry["version"] = version
        discovered[skill_name] = entry


def _skill_entry(
    skill_name: str,
    skill_config: dict[str, Any],
    usable_skills: dict[str, dict[str, Any]],
    advisory_skills: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    _validate_skill_entry_fields(skill_name, skill_config)
    entry = _build_skill_entry_base(skill_name, skill_config)
    if skill_config.get("always_available"):
        # Harness/process skills are guaranteed by the runtime, not the skills-root;
        # resolve them as usable without a filesystem probe (fixes orchestration=manual).
        return {**entry, "state": "usable_now", "root_kind": "harness", "skill_path": None}
    if skill_name in usable_skills:
        return {
            **entry,
            **_evaluate_installed_skill(
                skill_name, skill_config, usable_skills[skill_name]
            ),
        }
    if skill_name in advisory_skills:
        return _apply_advisory_state(entry, advisory_skills[skill_name])
    return _apply_installable_or_manual_state(entry)


def _install_command_for_skill(skill: dict[str, Any]) -> str | None:
    install_source = skill.get("install_source")
    if skill["source_type"] != "public" or not isinstance(install_source, dict):
        return None
    if install_source.get("method") == "skills_cli" and install_source.get("package"):
        return f"npx skills add {install_source['package']} -g -y"
    return None
