from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
}

CONFIG_DIR_NAME = "repo-audit-refactor-optimize"
DEFAULT_REPO_OVERRIDE = ".repo-audit-refactor-optimize/skill-sources.json"

# Shared domain constants used by scan_repo_profile and _matches_when.
KNOWN_LANGUAGES = frozenset({"python", "c", "rust", "assembly"})
KNOWN_TEST_SYSTEMS = frozenset({"pytest", "cargo", "cmake", "meson", "make"})
BENCHMARK_DIR_NAMES = frozenset({"benches", "benchmarks"})


def _env_value(env: dict[str, str] | None, key: str) -> str | None:
    if env is None:
        return os.environ.get(key)
    return env.get(key)


def _home_dir(env: dict[str, str] | None) -> Path:
    home = _env_value(env, "HOME")
    if home:
        return Path(home).expanduser()
    return Path.home()


def _default_user_override_path(env: dict[str, str] | None) -> Path:
    config_home = _env_value(env, "XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home).expanduser()
    else:
        base = _home_dir(env) / ".config"
    return base / CONFIG_DIR_NAME / "skill-sources.json"


def _default_orchestrator_home(env: dict[str, str] | None) -> Path:
    """Return the orchestrator skill home directory.

    Checks AGENT_SKILLS_HOME first (generic), then CODEX_HOME (backward
    compatibility with OpenAI Codex).  Falls back to ~/.codex when neither
    environment variable is set.
    """
    agent_home = _env_value(env, "AGENT_SKILLS_HOME")
    if agent_home:
        return Path(agent_home).expanduser()
    codex_home = _env_value(env, "CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser()
    return _home_dir(env) / ".codex"


def scan_repo_profile(repo_root: Path) -> dict[str, Any]:
    languages: set[str] = set()
    test_systems: set[str] = set()
    benchmark_surfaces: set[str] = set()

    for current_root, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = [name for name in dir_names if name not in SKIP_DIRS]
        basename_lower = os.path.basename(current_root).lower()

        if "pytest.ini" in file_names:
            test_systems.add("pytest")
        if "Cargo.toml" in file_names:
            test_systems.add("cargo")
            languages.add("rust")
        if "CMakeLists.txt" in file_names:
            test_systems.add("cmake")
        if "meson.build" in file_names:
            test_systems.add("meson")
        if "Makefile" in file_names or "GNUmakefile" in file_names:
            test_systems.add("make")

        parts_lower = {part.lower() for part in current_root.replace("\\", "/").split("/")}
        if basename_lower in BENCHMARK_DIR_NAMES:
            if any(name.endswith(".py") for name in file_names):
                benchmark_surfaces.add("python-benchmarks")
            if any(name.endswith(".rs") for name in file_names):
                benchmark_surfaces.add("cargo-benches")
            if any(os.path.splitext(name)[1].lower() in {".c", ".cc", ".cpp", ".h"} for name in file_names):
                benchmark_surfaces.add("native-benchmarks")

        for name in file_names:
            suffix = os.path.splitext(name)[1]
            lower_name = name.lower()

            if suffix == ".py":
                languages.add("python")
                if "bench" in lower_name or "benchmark" in lower_name or "benches" in parts_lower:
                    benchmark_surfaces.add("python-benchmarks")
            elif suffix in {".c", ".h"}:
                languages.add("c")
                if "bench" in lower_name or "perf" in lower_name or "benchmark" in parts_lower:
                    benchmark_surfaces.add("native-benchmarks")
            elif suffix == ".rs":
                languages.add("rust")
                if "bench" in lower_name or "benches" in parts_lower:
                    benchmark_surfaces.add("cargo-benches")
            elif suffix in {".s", ".S", ".asm"}:
                languages.add("assembly")
                if "bench" in lower_name or "perf" in lower_name:
                    benchmark_surfaces.add("native-benchmarks")

            if name == "pyproject.toml":
                languages.add("python")
                try:
                    content = Path(os.path.join(current_root, name)).read_text(encoding="utf-8")
                except OSError:
                    content = ""
                if "[tool.pytest.ini_options]" in content or "pytest" in content:
                    test_systems.add("pytest")

        if "tests" in parts_lower and any(name.endswith(".py") for name in file_names):
            languages.add("python")

    ordered_languages = [lang for lang in sorted(KNOWN_LANGUAGES) if lang in languages]
    ordered_tests = [name for name in sorted(KNOWN_TEST_SYSTEMS) if name in test_systems]
    ordered_benchmarks = [
        name
        for name in ["cargo-benches", "native-benchmarks", "python-benchmarks"]
        if name in benchmark_surfaces
    ]

    return {
        "languages": ordered_languages,
        "test_systems": ordered_tests,
        "benchmark_surfaces": ordered_benchmarks,
        "has_deterministic_test_surface": bool(ordered_tests),
        "has_deterministic_perf_surface": bool(ordered_benchmarks),
    }


def resolve_skill_roots(
    repo_root: Path,
    extra_roots: list[Path] | None = None,
    foreign_roots: list[Path] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, list[dict[str, str]]]:
    orchestrator_home = _default_orchestrator_home(env)
    home = _home_dir(env)
    candidate_roots = [
        ("orchestrator", orchestrator_home / "skills"),
        ("bundled", orchestrator_home / "vendor_imports" / "skills" / "skills"),
        ("user-local", home / ".agents" / "skills"),
        ("repo-local", repo_root / ".agents" / "skills"),
    ]
    if extra_roots:
        candidate_roots.extend(("extra", Path(root)) for root in extra_roots)

    usable_roots: list[dict[str, str]] = []
    advisory_roots: list[dict[str, str]] = []
    seen: set[Path] = set()

    for kind, root in candidate_roots:
        expanded = root.expanduser()
        if expanded.exists() and expanded not in seen:
            usable_roots.append({"kind": kind, "path": str(expanded)})
            seen.add(expanded)

    for root in foreign_roots or []:
        expanded = Path(root).expanduser()
        if expanded.exists() and expanded not in seen:
            advisory_roots.append({"kind": "foreign", "path": str(expanded)})
            seen.add(expanded)

    return {"usable_roots": usable_roots, "advisory_roots": advisory_roots}


def load_dependency_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed dependency manifest: {manifest_path}") from exc
    if not isinstance(payload, dict) or "skills" not in payload or "lanes" not in payload:
        raise ValueError(f"Invalid dependency manifest: {manifest_path}")
    return payload


_OVERRIDE_SCHEMA: dict[str, type] = {
    "source_type": str,
    "install_source": dict,
    "manual_fallback": str,
    "restart_required_if_installed": bool,
}


def _is_skill_override_valid(payload: dict[str, Any]) -> bool:
    return all(
        payload.get(field) is None or isinstance(payload[field], expected_type)
        for field, expected_type in _OVERRIDE_SCHEMA.items()
    )


def load_source_overrides(
    *,
    repo_root: Path,
    env: dict[str, str] | None,
    active_skill_names: set[str],
    strict_skill_names: set[str],
    user_override_path: Path | None = None,
    repo_override_path: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    warnings: list[str] = []
    merged: dict[str, dict[str, Any]] = {}
    sources = [
        ("user", user_override_path or _default_user_override_path(env)),
        ("repo", repo_override_path or (repo_root / DEFAULT_REPO_OVERRIDE)),
    ]

    for scope, path in sources:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed {scope} override file: {path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("skills"), dict):
            raise ValueError(f"Invalid {scope} override file: {path}")

        for skill_name, entry in payload["skills"].items():
            if not isinstance(entry, dict) or not _is_skill_override_valid(entry):
                if skill_name in strict_skill_names:
                    raise ValueError(f"Invalid override entry for required skill: {skill_name}")
                warnings.append(f"Ignored invalid override entry for {skill_name}.")
                continue
            if skill_name not in active_skill_names:
                warnings.append(f"Ignored override for unknown or inactive skill {skill_name}.")
                continue
            merged[skill_name] = entry

    return merged, warnings


def _extract_skill_name(skill_path: Path) -> str | None:
    try:
        with open(skill_path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(2048)
    except OSError:
        return None
    for line in head.splitlines()[:20]:
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def _discover_skills(roots: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    for root in roots:
        root_path = Path(root["path"])
        if not root_path.is_dir():
            continue
        try:
            entries = sorted(os.scandir(root_path), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir(follow_symlinks=True):
                continue
            skill_file = root_path / entry.name / "SKILL.md"
            if skill_file.exists():
                _register_skill(skill_file, root, root_path, discovered)
            else:
                # Support <root>/<subdir>/<skill>/SKILL.md (e.g. extra roots).
                sub_path = root_path / entry.name
                try:
                    sub_entries = sorted(os.scandir(sub_path), key=lambda e: e.name)
                except OSError:
                    continue
                for sub_entry in sub_entries:
                    if not sub_entry.is_dir(follow_symlinks=True):
                        continue
                    nested = sub_path / sub_entry.name / "SKILL.md"
                    if nested.exists():
                        _register_skill(nested, root, root_path, discovered)
    return discovered


def _register_skill(
    skill_file: Path,
    root: dict[str, str],
    root_path: Path,
    discovered: dict[str, dict[str, Any]],
) -> None:
    skill_name = _extract_skill_name(skill_file)
    if skill_name and skill_name not in discovered:
        discovered[skill_name] = {
            "root_kind": root["kind"],
            "root_path": str(root_path),
            "skill_path": str(skill_file),
        }


def _matches_when(profile: dict[str, Any], conditions: dict[str, Any]) -> bool:
    languages = set(profile["languages"])
    tests = set(profile["test_systems"])
    benchmarks = set(profile["benchmark_surfaces"])
    for key, expected in conditions.items():
        if key in KNOWN_LANGUAGES:
            if bool(expected) != (key in languages):
                return False
        elif key in KNOWN_TEST_SYSTEMS:
            if bool(expected) != (key in tests):
                return False
        elif key.startswith("has_deterministic_"):
            if bool(expected) != bool(profile.get(key)):
                return False
        elif key in benchmarks or bool(expected) is False:
            if bool(expected) != (key in benchmarks):
                return False
    return True


def _relevant_lane_names(profile: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    lane_names: list[str] = []
    for name, lane in manifest["lanes"].items():
        if lane.get("always"):
            lane_names.append(name)
        elif _matches_when(profile, lane.get("when", {})):
            lane_names.append(name)
    return lane_names


def _skill_entry(
    skill_name: str,
    skill_config: dict[str, Any],
    usable_skills: dict[str, dict[str, Any]],
    advisory_skills: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    entry = {
        "name": skill_name,
        "priority": skill_config["priority"],
        "source_type": skill_config["source_type"],
        "install_source": skill_config.get("install_source"),
        "manual_fallback": skill_config["manual_fallback"],
        "restart_required_if_installed": skill_config["restart_required_if_installed"],
    }

    if skill_name in usable_skills:
        discovered = usable_skills[skill_name]
        entry.update(
            {
                "state": "usable_now",
                "root_kind": discovered["root_kind"],
                "skill_path": discovered["skill_path"],
            }
        )
    elif skill_name in advisory_skills:
        discovered = advisory_skills[skill_name]
        entry.update(
            {
                "state": "advisory_only",
                "root_kind": discovered["root_kind"],
                "skill_path": discovered["skill_path"],
            }
        )
    elif entry["source_type"] == "public" and isinstance(entry["install_source"], dict):
        entry.update(
            {
                "state": "installable_now",
                "post_install_state": "available_next_run",
            }
        )
    else:
        entry["state"] = "manual_only"
    return entry


def _all_usable(names: list[str], skills: dict[str, dict[str, Any]]) -> bool:
    return all(skills[name]["state"] == "usable_now" for name in names)


def _usable_optionals(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> list[str]:
    return [name for name in lane.get("optional", []) if skills[name]["state"] == "usable_now"]


def _evaluate_test_lane(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    preferred = lane.get("preferred", [])
    fallback = lane.get("fallback", [])
    warnings: list[str] = []
    if preferred and _all_usable(preferred, skills):
        selected = list(preferred) + _usable_optionals(lane, skills)
        return "full", selected, warnings
    if fallback and _all_usable(fallback, skills):
        warnings.append("Preferred test audit skill unavailable; using fallback pair.")
        selected = list(fallback) + _usable_optionals(lane, skills)
        return "degraded", selected, warnings
    return "manual", [], warnings


def _evaluate_code_health_lane(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    if _all_usable(lane.get("preferred", []), skills):
        selected = list(lane.get("preferred", [])) + _usable_optionals(lane, skills)
        return "full", selected, []
    return "manual", [], []


def _evaluate_performance_lane(
    lane: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    if not profile["has_deterministic_perf_surface"]:
        if profile["has_deterministic_test_surface"]:
            warnings.append("No benchmark surface detected; performance work remains manual.")
            return "manual", [], warnings
        return "blocked", [], warnings

    if _all_usable(lane.get("preferred", []), skills):
        selected = list(lane.get("preferred", []))
        fallback = lane.get("fallback", [])
        if fallback and _all_usable(fallback, skills):
            selected.extend(fallback)
            selected.extend(_usable_optionals(lane, skills))
            return "full", selected, warnings
        warnings.append("Optimization skill missing; lane remains benchmark-first.")
        return "degraded", selected, warnings

    return "manual", [], warnings


def _evaluate_bootstrap_lane(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    if _all_usable(lane.get("preferred", []), skills):
        return "full", list(lane.get("preferred", [])), []
    return "degraded", [], ["Bootstrap helper skills unavailable; raw Skills CLI fallback required."]


def _evaluate_orchestration_lane(lane: dict[str, Any], skills: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    if _all_usable(lane.get("preferred", []), skills):
        selected = list(lane.get("preferred", [])) + _usable_optionals(lane, skills)
        return "full", selected, []
    return "manual", [], []


_LANE_EVALUATORS = {
    "test": lambda lane, skills, profile: _evaluate_test_lane(lane, skills),
    "code_health": lambda lane, skills, profile: _evaluate_code_health_lane(lane, skills),
    "performance": _evaluate_performance_lane,
    "bootstrap": lambda lane, skills, profile: _evaluate_bootstrap_lane(lane, skills),
    "orchestration": lambda lane, skills, profile: _evaluate_orchestration_lane(lane, skills),
}


def _evaluate_lane(
    lane_name: str,
    lane: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    lane_type = lane["lane_type"]
    evaluator = _LANE_EVALUATORS.get(lane_type, _LANE_EVALUATORS["orchestration"])
    state, selected, warnings = evaluator(lane, skills, profile)

    return {
        "lane_type": lane_type,
        "state": state,
        "selected_skills": selected,
        "manual_fallback": lane.get("manual_fallback"),
        "warnings": warnings,
        "blocking": bool(lane.get("blocking")) and state == "blocked",
    }


def _collect_active_and_strict_skills(
    active_lanes: list[str],
    manifest: dict[str, Any],
    required_skill_names: list[str] | None = None,
) -> tuple[set[str], set[str]]:
    active_skills = set(required_skill_names or [])
    strict_skills = set(required_skill_names or [])
    for lane_name in active_lanes:
        lane = manifest["lanes"][lane_name]
        active_skills.update(lane.get("preferred", []))
        active_skills.update(lane.get("fallback", []))
        active_skills.update(lane.get("optional", []))
        if lane.get("blocking"):
            strict_skills.update(lane.get("preferred", []))
            strict_skills.update(lane.get("fallback", []))
    return active_skills, strict_skills


def build_bootstrap_report(
    *,
    repo_root: Path,
    manifest_path: Path,
    out_dir: Path,
    env: dict[str, str] | None = None,
    extra_roots: list[Path] | None = None,
    foreign_roots: list[Path] | None = None,
    user_override_path: Path | None = None,
    repo_override_path: Path | None = None,
    required_skill_names: list[str] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    out_dir = out_dir.resolve()
    manifest = load_dependency_manifest(manifest_path)
    profile = scan_repo_profile(repo_root)
    active_lanes = _relevant_lane_names(profile, manifest)
    active_skills, strict_skills = _collect_active_and_strict_skills(
        active_lanes, manifest, required_skill_names,
    )

    overrides, warnings = load_source_overrides(
        repo_root=repo_root,
        env=env,
        active_skill_names=active_skills,
        strict_skill_names=strict_skills,
        user_override_path=user_override_path,
        repo_override_path=repo_override_path,
    )
    roots = resolve_skill_roots(repo_root, extra_roots=extra_roots, foreign_roots=foreign_roots, env=env)
    usable_skills = _discover_skills(roots["usable_roots"])
    advisory_skills = _discover_skills(roots["advisory_roots"])

    merged_skills: dict[str, dict[str, Any]] = {}
    for skill_name in sorted(active_skills):
        skill_config = dict(manifest["skills"][skill_name])
        if skill_name in overrides:
            skill_config.update(overrides[skill_name])
        merged_skills[skill_name] = _skill_entry(skill_name, skill_config, usable_skills, advisory_skills)

    lanes: dict[str, dict[str, Any]] = {}
    for lane_name in active_lanes:
        lanes[lane_name] = _evaluate_lane(lane_name, manifest["lanes"][lane_name], merged_skills, profile)
        warnings.extend(lanes[lane_name]["warnings"])

    blocking_skill_names: set[str] = set()
    for lane_name, lane_result in lanes.items():
        if not lane_result["blocking"]:
            continue
        lane_config = manifest["lanes"][lane_name]
        blocking_skill_names.update(lane_config.get("preferred", []))
        blocking_skill_names.update(lane_config.get("fallback", []))
    for skill_name in blocking_skill_names:
        if merged_skills[skill_name]["state"] == "manual_only":
            merged_skills[skill_name]["state"] = "blocking_missing"

    install_candidates = [
        {
            "name": skill_name,
            "command": _install_command_for_skill(skill),
            "post_install_state": skill.get("post_install_state"),
            "restart_required": skill["restart_required_if_installed"],
            "source_type": skill["source_type"],
        }
        for skill_name, skill in merged_skills.items()
        if skill["state"] == "installable_now" and _install_command_for_skill(skill)
    ]

    stop_before_discovery = any(lane["blocking"] for lane in lanes.values())
    restart_required = any(item["restart_required"] for item in install_candidates if item["post_install_state"] == "available_next_run")

    return {
        "repo_root": str(repo_root),
        "artifact_root": str(out_dir / "bootstrap"),
        "repo_profile": profile,
        "roots": roots,
        "skills": merged_skills,
        "lanes": lanes,
        "install_candidates": install_candidates,
        "summary": {
            "stop_before_discovery": stop_before_discovery,
            "restart_required": restart_required,
            "active_lanes": active_lanes,
        },
        "warnings": sorted(set(warnings)),
    }


def _install_command_for_skill(skill: dict[str, Any]) -> str | None:
    install_source = skill.get("install_source")
    if skill["source_type"] != "public" or not isinstance(install_source, dict):
        return None
    if install_source.get("method") == "skills_cli" and install_source.get("package"):
        return f"npx skills add {install_source['package']} -g -y"
    return None


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Bootstrap Report",
        "",
        f"- Repo: `{report['repo_root']}`",
        f"- Active lanes: {', '.join(report['summary']['active_lanes']) or 'none'}",
        f"- Stop before discovery: `{str(report['summary']['stop_before_discovery']).lower()}`",
        f"- Restart required after blocking installs: `{str(report['summary']['restart_required']).lower()}`",
        "",
        "## Lane States",
        "",
    ]
    for lane_name, lane in report["lanes"].items():
        lines.append(f"- `{lane_name}`: `{lane['state']}`")
        if lane["selected_skills"]:
            lines.append(f"  selected: {', '.join(f'`{name}`' for name in lane['selected_skills'])}")
    lines.extend(["", "## Skill States", ""])
    for skill_name, skill in report["skills"].items():
        lines.append(f"- `{skill_name}`: `{skill['state']}`")
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def _markdown_install_plan(report: dict[str, Any]) -> str:
    lines = [
        "# Install Plan",
        "",
        "This checker never installs skills. Use the commands below only after explicit approval.",
        "",
    ]
    if not report["install_candidates"]:
        lines.append("No public install candidates were detected.")
        lines.append("")
        return "\n".join(lines)

    for candidate in report["install_candidates"]:
        lines.append(f"## `{candidate['name']}`")
        lines.append("")
        lines.append(f"- Command: `{candidate['command']}`")
        lines.append(f"- Post-install state: `{candidate['post_install_state']}`")
        lines.append(
            f"- Restart required before reuse: `{str(candidate['restart_required']).lower()}`"
        )
        lines.append("")
    return "\n".join(lines)


def write_bootstrap_outputs(report: dict[str, Any], out_dir: Path) -> None:
    bootstrap_dir = out_dir / "bootstrap"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)
    (bootstrap_dir / "bootstrap_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (bootstrap_dir / "bootstrap_report.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    (bootstrap_dir / "install_plan.md").write_text(
        _markdown_install_plan(report),
        encoding="utf-8",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check metaskill bootstrap requirements.")
    parser.add_argument("--repo", required=True, type=Path, help="Repository root to scan.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("skill_bootstrap_manifest.json"),
        help="Dependency manifest path.",
    )
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory root.")
    parser.add_argument("--extra-root", action="append", default=[], type=Path)
    parser.add_argument("--foreign-root", action="append", default=[], type=Path)
    parser.add_argument("--user-override", type=Path)
    parser.add_argument("--repo-override", type=Path)
    parser.add_argument("--require-skill", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_bootstrap_report(
        repo_root=args.repo,
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        extra_roots=args.extra_root,
        foreign_roots=args.foreign_root,
        user_override_path=args.user_override,
        repo_override_path=args.repo_override,
        required_skill_names=args.require_skill,
    )
    write_bootstrap_outputs(report, args.out_dir)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
