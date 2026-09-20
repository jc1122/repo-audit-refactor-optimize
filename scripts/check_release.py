#!/usr/bin/env python3
"""Release-gate checks for the thin 1.0.1 skill.

Verifies: SKILL.md Agent Skills frontmatter (name + metadata.version semver),
CHANGELOG heading, wrapper version sync, installer pin sync, shipped reference
set, and absence of retired v0.x runtime machinery.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

EXPECTED_VERSION = "1.0.1"

CORE_REQUIRES_FLOOR = "1.0.0"

REQUIRED_REFERENCES = (
    "acceptance.md",
    "prioritization.md",
    "remediation-playbook.md",
    "verification.md",
    "MIGRATION.md",
)

# v0.x runtime machinery that must not ship in 1.0.0. The acceptance policy
# implementation (_accept.py, validate_accept.py, schema) was removed after
# the core migrated all 41 acceptance tests (see STATUS-orchestrator.md);
# only the user-facing acceptance doc stays.
RETIRED_SCRIPTS = (
    "mprr_run.py",
    "mprr_gate.py",
    "mprr_integrate.py",
    "mprr_normalize.py",
    "mprr_packets.py",
    "mprr_partition.py",
    "mprr_schedule.py",
    "synth_run.py",
    "synthesize_packets.py",
    "synthesize_perf.py",
    "graduate_benchmark.py",
    "mine_iteration_kpis.py",
    "allocate_batches.py",
    "run_instruction_eval.py",
    "_lane_resolve.py",
    "_skill_probe.py",
    "_bootstrap_report.py",
    "_wave_findings.py",
    "check_skill_requirements.py",
    "_accept.py",
    "validate_accept.py",
    "check_wave_baseline.py",
    "check_coverage_gap.py",
    "check_mutation_floor.py",
    "check_accept_reasons.py",
    "check_toolchain.py",
    "validate_run_report.py",
    "migrate_baseline_to_accept.py",
)

RETIRED_FILES = (
    "schema/accept.schema.json",
    "scripts/skill_bootstrap_manifest.json",
    "scripts/wave_lanes.json",
    "scripts/toolchain_pins.json",
    "scripts/growth_allowances.json",
    "scripts/mutation_targets.json",
    "scripts/coverage_gap_baseline.json",
    "scripts/hotspot_audit_config.json",
    "scripts/wave_anchor.txt",
    "scripts/wave_frozen.md",
)


def frontmatter(path: Path) -> dict[str, object]:
    """Parse SKILL.md YAML frontmatter, supporting one nested mapping level."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} does not start with YAML frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"{path} has unterminated YAML frontmatter")
    values: dict[str, object] = {}
    current_parent: str | None = None
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and ":" in line:
            key, raw = line.split(":", 1)
            key, raw = key.strip(), raw.strip().strip('"')
            if raw == "":
                values[key] = {}
                current_parent = key
            else:
                values[key] = raw
                current_parent = None
        elif indent > 0 and current_parent is not None and ":" in line:
            sub = values[current_parent]
            assert isinstance(sub, dict)
            key, raw = line.strip().split(":", 1)
            sub[key.strip()] = raw.strip().strip('"')
    return values


def _check_requires(meta: dict[str, object]) -> list[str]:
    """Validate metadata.requires names repo-audit-checks with a 1.0.0 floor."""
    metadata = meta.get("metadata")
    requires = metadata.get("requires") if isinstance(metadata, dict) else ""
    if not isinstance(requires, str) or not requires.strip():
        return ["SKILL.md metadata.requires must declare the core dependency"]
    parts = requires.strip().split()
    if len(parts) != 3 or parts[0] != "repo-audit-checks" or parts[1] not in ("==", ">="):
        return [
            "SKILL.md metadata.requires must look like "
            "'repo-audit-checks >= 1.0.0' (got %r)" % requires
        ]
    if not SEMVER_RE.match(parts[2]) or parts[2] != CORE_REQUIRES_FLOOR:
        return [
            "SKILL.md metadata.requires floor must stay "
            f"'{CORE_REQUIRES_FLOOR}' (core repo is still v{CORE_REQUIRES_FLOOR}; "
            f"got {parts[2]!r})"
        ]
    return []


def _metadata_version(meta: dict[str, object]) -> str:
    metadata = meta.get("metadata")
    if isinstance(metadata, dict):
        version = metadata.get("version", "")
        return version if isinstance(version, str) else ""
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check 1.0.1 release readiness.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root (default: script's parent directory)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    defects: list[str] = []

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

    if meta.get("name") != "repo-audit-refactor-optimize":
        defects.append("SKILL.md frontmatter 'name' must be repo-audit-refactor-optimize")
    if "version" in meta:
        defects.append("SKILL.md must use metadata.version, not top-level 'version:'")
    version = _metadata_version(meta)
    if not version:
        defects.append("SKILL.md frontmatter missing 'metadata.version'")
    elif not SEMVER_RE.match(version):
        defects.append(f"metadata.version '{version}' is not valid semver (X.Y.Z)")
    elif version != EXPECTED_VERSION:
        defects.append(f"metadata.version '{version}' != expected '{EXPECTED_VERSION}'")

    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        defects.append(f"CHANGELOG.md not found at {changelog}")
    elif f"## {EXPECTED_VERSION}" not in changelog.read_text(encoding="utf-8"):
        defects.append(f"CHANGELOG.md missing heading '## {EXPECTED_VERSION}'")

    skill_text = skill_path.read_text(encoding="utf-8")
    for verb in ("doctor", "scan", "compare"):
        if f'scripts/repo-audit" {verb}' not in skill_text:
            defects.append(f"SKILL.md must show the scripts/repo-audit launcher for {verb}")

    wrapper = root / "scripts" / "run_diagnosis_wave.py"
    if wrapper.exists():
        text = wrapper.read_text(encoding="utf-8")
        if f'__version__ = "{EXPECTED_VERSION}"' not in text:
            defects.append(
                f"run_diagnosis_wave.__version__ != '{EXPECTED_VERSION}'"
            )
    else:
        defects.append("scripts/run_diagnosis_wave.py wrapper missing")

    installer = root / "bootstrap" / "install.sh"
    if not installer.exists():
        defects.append("bootstrap/install.sh missing")
    else:
        install_text = installer.read_text(encoding="utf-8")
        if f'SKILL_VERSION="{EXPECTED_VERSION}"' not in install_text:
            defects.append("bootstrap/install.sh SKILL_VERSION pin drift")
        if "repo-audit-skills@v1.0.0" not in install_text:
            defects.append("bootstrap/install.sh core pin drift (expected v1.0.0)")
        if "--break-system-packages" in install_text:
            defects.append("bootstrap/install.sh must never bypass PEP 668")
        if "-m venv" not in install_text or "-m pip install" not in install_text:
            defects.append("bootstrap/install.sh must install the core into an isolated venv")
    launcher = root / "scripts" / "repo-audit"
    if not launcher.exists():
        defects.append("scripts/repo-audit launcher missing")
    defects.extend(_check_requires(meta))

    for ref in REQUIRED_REFERENCES:
        if not (root / "references" / ref).exists():
            defects.append(f"references/{ref} missing")
    for retired in ("bootstrap.md", "activation-matrix.md", "pipeline.md", "mprr.md"):
        if (root / "references" / retired).exists():
            defects.append(f"references/{retired} is retired v0.x prose and must go")

    scripts_dir = root / "scripts"
    for name in RETIRED_SCRIPTS:
        if (scripts_dir / name).exists():
            defects.append(f"scripts/{name} is retired machinery and must be removed")
    for rel in RETIRED_FILES:
        if (root / rel).exists():
            defects.append(f"{rel} is retired and must be removed")

    if defects:
        print(json.dumps({"status": "fail", "defects": defects}))
        return 1
    print(json.dumps({"status": "pass"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
