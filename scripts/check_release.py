#!/usr/bin/env python3
"""Release-gate checks: version-sync across SKILL.md, CHANGELOG, and manifest."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
MANIFEST_PATH = "scripts" / Path("skill_bootstrap_manifest.json")


def frontmatter(path: Path) -> dict[str, str]:
    """Parse SKILL.md YAML frontmatter. Raises ValueError on malformed input."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} does not start with YAML frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"{path} has unterminated YAML frontmatter")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        values[key.strip()] = raw.strip().strip('"')
    return values


def _check_semver(version: str, skill_path: Path) -> list[str]:
    """Validate version matches semver; returns list of defect strings."""
    defects: list[str] = []
    if not SEMVER_RE.match(version):
        defects.append(
            f"SKILL.md version '{version}' is not valid semver (expected X.Y.Z)"
        )
    return defects


def _check_changelog(root: Path, version: str) -> list[str]:
    """Check CHANGELOG.md exists and contains ## <version> heading."""
    defects: list[str] = []
    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        defects.append(f"CHANGELOG.md not found at {changelog}")
        return defects
    heading = f"## {version}"
    text = changelog.read_text(encoding="utf-8")
    if heading not in text:
        defects.append(
            f"CHANGELOG.md missing heading '{heading}' for version {version}"
        )
    return defects


def _check_manifest(root: Path) -> list[str]:
    """Check manifest exists, parses as JSON, has 'skills' and 'lanes' keys."""
    defects: list[str] = []
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.exists():
        defects.append(f"Manifest file not found at {manifest_path}")
        return defects
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        defects.append(f"Manifest file at {manifest_path} is invalid JSON: {exc}")
        return defects
    if not isinstance(data, dict):
        defects.append(f"Manifest file at {manifest_path} is not a JSON object")
        return defects
    if "skills" not in data:
        defects.append(f"Manifest file at {manifest_path} missing 'skills' key")
    if "lanes" not in data:
        defects.append(f"Manifest file at {manifest_path} missing 'lanes' key")
    return defects


def _check_runner_version_sync(version: str) -> list[str]:
    """Runner __version__ must equal the SKILL.md version (#8 pin-coherence)."""
    runner = importlib.import_module(
        "scripts.run_diagnosis_wave" if __package__ else "run_diagnosis_wave"
    )
    runner_version = getattr(runner, "__version__", "")
    if runner_version != version:
        return [
            f"run_diagnosis_wave.__version__ '{runner_version}' "
            f"!= SKILL.md version '{version}'"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check release readiness: version-sync across artifacts."
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root (default: script's parent directory)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    defects: list[str] = []

    # 1. Parse version from SKILL.md frontmatter
    skill_path = root / "SKILL.md"
    if not skill_path.exists():
        defects.append(f"SKILL.md not found at {skill_path}")
        print(json.dumps({"status": "fail", "defects": defects}))
        return 1

    try:
        meta = frontmatter(skill_path)
    except (ValueError, OSError) as exc:
        defects.append(f"Failed to parse SKILL.md frontmatter: {exc}")
        print(json.dumps({"status": "fail", "defects": defects}))
        return 1

    version = meta.get("version", "")
    if not version:
        defects.append("SKILL.md frontmatter missing 'version' key")
        print(json.dumps({"status": "fail", "defects": defects}))
        return 1

    # 2. Validate semver
    defects.extend(_check_semver(version, skill_path))

    # 3. Check CHANGELOG
    defects.extend(_check_changelog(root, version))

    # 4. Check manifest
    defects.extend(_check_manifest(root))

    # 5. Runner version-sync (#8): only when --root owns the runner module.
    if (root / "scripts" / "run_diagnosis_wave.py").exists():
        defects.extend(_check_runner_version_sync(version))

    if defects:
        print(json.dumps({"status": "fail", "defects": defects}))
        return 1

    print(json.dumps({"status": "pass"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
