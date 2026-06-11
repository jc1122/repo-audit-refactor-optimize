from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from scripts._skill_probe import (
        _REQUIRED_SKILL_FIELDS,
        _discover_skills,
        _extract_skill_meta,
        _extract_skill_name,
        _install_command_for_skill,
        _parse_version,
        _register_skill,
        _scan_skill_root,
        _scan_skill_subdir,
        _skill_entry,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts._skill_probe import (
        _REQUIRED_SKILL_FIELDS,
        _discover_skills,
        _extract_skill_meta,
        _extract_skill_name,
        _install_command_for_skill,
        _parse_version,
        _register_skill,
        _scan_skill_root,
        _scan_skill_subdir,
        _skill_entry,
    )
try:
    from scripts._lane_resolve import (
        CONFIG_DIR_NAME,
        DEFAULT_REPO_OVERRIDE,
        KNOWN_LANGUAGES,
        KNOWN_TEST_SYSTEMS,
        _LANE_EVALUATORS,
        _all_usable,
        _build_install_candidates,
        _build_merged_skills,
        _collect_active_and_strict_skills,
        _default_orchestrator_home,
        _default_user_override_path,
        _env_value,
        _evaluate_bootstrap_lane,
        _evaluate_code_health_lane,
        _evaluate_coverage_lane,
        _evaluate_lane,
        _evaluate_orchestration_lane,
        _evaluate_performance_lane,
        _evaluate_preferred_fallback_lane,
        _evaluate_test_lane,
        _home_dir,
        _is_skill_override_valid,
        _mark_blocking_skills,
        _matches_when,
        _OVERRIDE_SCHEMA,
        _read_override_payload,
        _relevant_lane_names,
        _usable_optionals,
        load_dependency_manifest,
        load_source_overrides,
        resolve_skill_roots,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts._lane_resolve import (
        CONFIG_DIR_NAME,
        DEFAULT_REPO_OVERRIDE,
        KNOWN_LANGUAGES,
        KNOWN_TEST_SYSTEMS,
        _LANE_EVALUATORS,
        _all_usable,
        _build_install_candidates,
        _build_merged_skills,
        _collect_active_and_strict_skills,
        _default_orchestrator_home,
        _default_user_override_path,
        _env_value,
        _evaluate_bootstrap_lane,
        _evaluate_code_health_lane,
        _evaluate_coverage_lane,
        _evaluate_lane,
        _evaluate_orchestration_lane,
        _evaluate_performance_lane,
        _evaluate_preferred_fallback_lane,
        _evaluate_test_lane,
        _home_dir,
        _is_skill_override_valid,
        _mark_blocking_skills,
        _matches_when,
        _OVERRIDE_SCHEMA,
        _read_override_payload,
        _relevant_lane_names,
        _usable_optionals,
        load_dependency_manifest,
        load_source_overrides,
        resolve_skill_roots,
    )


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

# ---------------------------------------------------------------------------
# Lookup tables for file classification and benchmark detection
# ---------------------------------------------------------------------------
_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".c": "c",
    ".h": "c",
    ".cc": "c",
    ".cpp": "c",
    ".hpp": "c",
    ".rs": "rust",
    ".s": "assembly",
    ".S": "assembly",
    ".asm": "assembly",
}

_BENCH_NAME_KW: dict[str, tuple[str, ...]] = {
    ".py": ("bench", "benchmark"),
    ".c": ("bench", "perf"),
    ".h": ("bench", "perf"),
    ".cc": ("bench", "perf"),
    ".cpp": ("bench", "perf"),
    ".hpp": ("bench", "perf"),
    ".rs": ("bench",),
    ".s": ("bench", "perf"),
    ".S": ("bench", "perf"),
    ".asm": ("bench", "perf"),
}

_BENCH_PATH_KW: dict[str, tuple[str, ...]] = {
    ".py": ("benches",),
    ".c": ("benchmark",),
    ".h": ("benchmark",),
    ".cc": ("benchmark",),
    ".cpp": ("benchmark",),
    ".hpp": ("benchmark",),
    ".rs": ("benches",),
}

_BENCH_SURFACE: dict[str, str] = {
    ".py": "python-benchmarks",
    ".c": "native-benchmarks",
    ".h": "native-benchmarks",
    ".cc": "native-benchmarks",
    ".cpp": "native-benchmarks",
    ".hpp": "native-benchmarks",
    ".rs": "cargo-benches",
    ".s": "native-benchmarks",
    ".S": "native-benchmarks",
    ".asm": "native-benchmarks",
}


def _has_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    """Return True when *text* contains any of the given *keywords*."""
    return any(kw in text for kw in keywords)


def _dir_marker_contributions(
    file_names: list[str],
) -> tuple[set[str], set[str]]:
    """Detect test systems and languages from directory marker files."""
    test_systems: set[str] = set()
    languages: set[str] = set()

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

    return test_systems, languages


def _ordered_list(allowed_order: list[str], found_set: set[str]) -> list[str]:
    """Return items from *allowed_order* that are also in *found_set*."""
    return [item for item in allowed_order if item in found_set]


def _has_any_suffix_py(file_names: list[str]) -> bool:
    """Return True when any file in *file_names* ends with '.py'."""
    return any(name.endswith(".py") for name in file_names)


def _benchmark_surface(
    suffix: str, lower_name: str, parts_lower: set[str]
) -> str | None:
    """Return the benchmark surface for a file, or None."""
    bench_kws = _BENCH_NAME_KW.get(suffix)
    if bench_kws and _has_any_keyword(lower_name, bench_kws):
        return _BENCH_SURFACE.get(suffix)
    path_kws = _BENCH_PATH_KW.get(suffix)
    if path_kws:
        for kw in path_kws:
            if kw in parts_lower:
                return _BENCH_SURFACE.get(suffix)
    return None


def _classify_file_full(
    name: str, parts_lower: set[str]
) -> tuple[str | None, str | None]:
    """Classify a single source file: (language, benchmark_surface)."""
    suffix = os.path.splitext(name)[1]
    lang = _LANG_MAP.get(suffix)
    if lang is None:
        return None, None
    return lang, _benchmark_surface(suffix, name.lower(), parts_lower)


def _path_parts_lower(current_root: str, repo_root: Path) -> set[str]:
    """Compute the lowercased path components relative to *repo_root*."""
    rel = os.path.relpath(current_root, repo_root)
    return {part.lower() for part in rel.replace("\\", "/").split("/")}


def _is_python_test_dir(parts_lower: set[str], file_names: list[str]) -> bool:
    """Return True when the directory looks like a Python test directory."""
    return "tests" in parts_lower and _has_any_suffix_py(file_names)


def _pyproject_contributions(pyproject_path: Path) -> tuple[set[str], set[str]]:
    """Return (languages, test_systems) contributions from a pyproject.toml."""
    languages = {"python"}
    test_systems: set[str] = set()
    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return languages, test_systems
    if "[tool.pytest.ini_options]" in content or "pytest" in content:
        test_systems.add("pytest")
    return languages, test_systems


def scan_repo_profile(repo_root: Path) -> dict[str, Any]:
    """Scan a repository to detect languages, test systems, and benchmark surfaces."""
    languages: set[str] = set()
    test_systems: set[str] = set()
    benchmark_surfaces: set[str] = set()

    for current_root, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = [name for name in dir_names if name not in SKIP_DIRS]

        ts, langs = _dir_marker_contributions(file_names)
        test_systems.update(ts)
        languages.update(langs)

        parts_lower = _path_parts_lower(current_root, repo_root)

        for name in file_names:
            lang, bench = _classify_file_full(name, parts_lower)
            if lang:
                languages.add(lang)
            if bench:
                benchmark_surfaces.add(bench)

            if name == "pyproject.toml":
                langs2, ts2 = _pyproject_contributions(
                    Path(os.path.join(current_root, name))
                )
                languages.update(langs2)
                test_systems.update(ts2)

        if _is_python_test_dir(parts_lower, file_names):
            languages.add("python")

    ordered_languages = _ordered_list(sorted(KNOWN_LANGUAGES), languages)
    ordered_tests = _ordered_list(sorted(KNOWN_TEST_SYSTEMS), test_systems)
    ordered_benchmarks = _ordered_list(
        ["cargo-benches", "native-benchmarks", "python-benchmarks"],
        benchmark_surfaces,
    )

    return {
        "languages": ordered_languages,
        "test_systems": ordered_tests,
        "benchmark_surfaces": ordered_benchmarks,
        "has_deterministic_test_surface": bool(ordered_tests),
        "has_deterministic_perf_surface": bool(ordered_benchmarks),
    }


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
    """Build the full bootstrap report for a repository."""
    repo_root = repo_root.resolve()
    out_dir = out_dir.resolve()
    if not repo_root.exists():
        raise ValueError(f"Repository root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"Repository root is not a directory: {repo_root}")
    manifest = load_dependency_manifest(manifest_path)
    profile = scan_repo_profile(repo_root)
    active_lanes = _relevant_lane_names(profile, manifest)
    active_skills, strict_skills = _collect_active_and_strict_skills(
        active_lanes,
        manifest,
        required_skill_names,
    )

    overrides, warnings = load_source_overrides(
        repo_root=repo_root,
        env=env,
        active_skill_names=active_skills,
        strict_skill_names=strict_skills,
        user_override_path=user_override_path,
        repo_override_path=repo_override_path,
    )
    roots = resolve_skill_roots(
        repo_root, extra_roots=extra_roots, foreign_roots=foreign_roots, env=env
    )
    usable_skills = _discover_skills(roots["usable_roots"])
    advisory_skills = _discover_skills(roots["advisory_roots"])
    unreferenced_skills = sorted(
        set(usable_skills) - set(manifest["skills"])
    )

    merged_skills = _build_merged_skills(
        active_skills, manifest, overrides, usable_skills, advisory_skills
    )

    lanes: dict[str, dict[str, Any]] = {}
    for lane_name in active_lanes:
        lanes[lane_name] = _evaluate_lane(
            lane_name, manifest["lanes"][lane_name], merged_skills, profile
        )
        warnings.extend(lanes[lane_name]["warnings"])

    # Fold per-skill entry warnings into the top-level warnings list.
    for skill in merged_skills.values():
        if "warnings" in skill:
            warnings.extend(skill["warnings"])

    _mark_blocking_skills(lanes, manifest, merged_skills)
    install_candidates = _build_install_candidates(merged_skills)

    stop_before_discovery = any(lane["blocking"] for lane in lanes.values())
    restart_required = any(
        item["restart_required"]
        for item in install_candidates
        if item["post_install_state"] == "available_next_run"
        and item["name"] in strict_skills
    )

    return {
        "repo_root": str(repo_root),
        "artifact_root": str(out_dir / "bootstrap"),
        "repo_profile": profile,
        "roots": roots,
        "skills": merged_skills,
        "lanes": lanes,
        "install_candidates": install_candidates,
        "unreferenced_skills": unreferenced_skills,
        "summary": {
            "stop_before_discovery": stop_before_discovery,
            "restart_required": restart_required,
            "active_lanes": active_lanes,
        },
        "warnings": sorted(set(warnings)),
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Bootstrap Report",
        "",
        f"- Repo: `{report['repo_root']}`",
        f"- Active lanes: {', '.join(report['summary']['active_lanes']) or 'none'}",
        f"- Stop before discovery: "
        f"`{str(report['summary']['stop_before_discovery']).lower()}`",
        f"- Restart required before using strict installs: "
        f"`{str(report['summary']['restart_required']).lower()}`",
        "",
        "## Lane States",
        "",
    ]
    for lane_name, lane in report["lanes"].items():
        lines.append(f"- `{lane_name}`: `{lane['state']}`")
        if lane["selected_skills"]:
            lines.append(
                f"  selected: "
                f"{', '.join(f'`{name}`' for name in lane['selected_skills'])}"
            )
    lines.extend(["", "## Skill States", ""])
    for skill_name, skill in report["skills"].items():
        lines.append(f"- `{skill_name}`: `{skill['state']}`")
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    if report.get("unreferenced_skills"):
        lines.extend(["", "## Unreferenced Skills (advisory)", ""])
        for name in report["unreferenced_skills"]:
            lines.append(f"- `{name}`")
    lines.append("")
    return "\n".join(lines)


def _markdown_install_plan(report: dict[str, Any]) -> str:
    lines = [
        "# Install Plan",
        "",
        "This checker never installs skills. Use the commands below "
        "only after explicit approval.",
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
            f"- Restart required before reuse: "
            f"`{str(candidate['restart_required']).lower()}`"
        )
        lines.append("")
    return "\n".join(lines)


def write_bootstrap_outputs(report: dict[str, Any], out_dir: Path) -> None:
    """Write JSON report, Markdown report, and install plan to the output directory."""
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
    parser = argparse.ArgumentParser(
        description="Check metaskill bootstrap requirements."
    )
    parser.add_argument(
        "--repo", required=True, type=Path, help="Repository root to scan."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("skill_bootstrap_manifest.json"),
        help="Dependency manifest path.",
    )
    parser.add_argument(
        "--out-dir", required=True, type=Path, help="Output directory root."
    )
    parser.add_argument("--extra-root", action="append", default=[], type=Path)
    parser.add_argument("--foreign-root", action="append", default=[], type=Path)
    parser.add_argument("--user-override", type=Path)
    parser.add_argument("--repo-override", type=Path)
    parser.add_argument("--require-skill", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
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
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    write_bootstrap_outputs(report, args.out_dir)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
