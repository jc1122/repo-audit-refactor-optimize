from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, TypedDict

from scripts._lane_resolve import (
    KNOWN_LANGUAGES,
    KNOWN_TEST_SYSTEMS,
    _build_install_candidates,
    _build_merged_skills,
    _collect_active_and_strict_skills,
    _evaluate_lane,
    _mark_blocking_skills,
    _relevant_lane_names,
    load_dependency_manifest,
    load_source_overrides,
    resolve_skill_roots,
)
from scripts._skill_probe import _discover_skills


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

_BENCH_PATH_KW: dict[str, tuple[str, ...]] = {
    ".py": ("benches", "benchmarks"),
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


class _CollectDiscoveryInput(TypedDict):
    env: dict[str, str] | None
    active_skills: set[str]
    strict_skills: set[str]
    user_override_path: Path | None
    repo_override_path: Path | None
    extra_roots: list[Path] | None
    foreign_roots: list[Path] | None


class _CollectDiscoveryOutput(TypedDict):
    warnings: list[str]
    roots: dict[str, list[dict[str, str]]]
    merged_skills: dict[str, dict[str, Any]]
    unreferenced_skills: list[str]


class _ReportPayloadContext(TypedDict):
    repo_root: Path
    out_dir: Path
    profile: dict[str, Any]
    active_lanes: list[str]
    strict_skills: set[str]
    roots: dict[str, list[dict[str, str]]]
    warnings: list[str]
    merged_skills: dict[str, dict[str, Any]]
    lanes: dict[str, dict[str, Any]]
    install_candidates: list[dict[str, Any]]
    unreferenced_skills: list[str]


class _BuildBootstrapOptions(TypedDict):
    env: dict[str, str] | None
    extra_roots: list[Path] | None
    foreign_roots: list[Path] | None
    user_override_path: Path | None
    repo_override_path: Path | None
    required_skill_names: list[str] | None


@dataclass(frozen=True)
class BootstrapReportRequest:
    """Inputs required to build a bootstrap report."""

    repo_root: Path
    manifest_path: Path
    out_dir: Path
    env: dict[str, str] | None = None
    extra_roots: list[Path] | None = None
    foreign_roots: list[Path] | None = None
    user_override_path: Path | None = None
    repo_override_path: Path | None = None
    required_skill_names: list[str] | None = None


def _coerce_bootstrap_report_request(
    request: BootstrapReportRequest | None,
    kwargs: dict[str, Any],
) -> BootstrapReportRequest:
    if request is not None:
        if kwargs:
            names = ", ".join(sorted(kwargs))
            raise TypeError(
                "build_bootstrap_report accepts either a BootstrapReportRequest "
                f"or keyword arguments, not both: {names}"
            )
        return request
    return BootstrapReportRequest(**kwargs)


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


# Directories that hold tooling or tests — never a benchmark *surface*.
_NON_SURFACE_DIRS: frozenset[str] = frozenset({"scripts", "tests"})


def _is_harness_name(lower_name: str, suffix: str) -> bool:
    """True for the benchmark harness naming convention:
    ``bench_*.<ext>`` or ``bench.<ext>``."""
    return lower_name.startswith("bench_") or lower_name == f"bench{suffix}"


def _benchmark_surface(
    suffix: str, lower_name: str, parts_lower: set[str]
) -> str | None:
    """Return the benchmark surface for a file, or None.

    A file counts as a benchmark *surface* only when it follows the harness naming
    convention (``bench_*.<ext>``) OR sits under a benchmark directory — and is not
    under a tooling/test directory. This stops source/tests that merely mention
    "benchmark" (e.g. ``scripts/graduate_benchmark.py``) from being mistaken for a
    committed benchmark surface.
    """
    if parts_lower & _NON_SURFACE_DIRS:
        return None
    if suffix in _BENCH_SURFACE and _is_harness_name(lower_name, suffix):
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


def _normalize_repo_root(repo_root: Path) -> Path:
    """Normalize and validate repository root path."""
    normalized_root = repo_root.resolve()
    if not normalized_root.exists():
        raise ValueError(f"Repository root does not exist: {normalized_root}")
    if not normalized_root.is_dir():
        raise ValueError(f"Repository root is not a directory: {normalized_root}")
    return normalized_root


def _collect_active_skills(
    profile: dict[str, Any],
    manifest: dict[str, Any],
    required_skill_names: list[str] | None,
) -> tuple[list[str], set[str], set[str]]:
    """Collect lane activity and active/strict skill names."""
    active_lanes = _relevant_lane_names(profile, manifest)
    active_skills, strict_skills = _collect_active_and_strict_skills(
        active_lanes,
        manifest,
        required_skill_names,
    )
    return active_lanes, active_skills, strict_skills


def _collect_discovery_inputs(
    repo_root: Path,
    manifest: dict[str, Any],
    options: _CollectDiscoveryInput,
) -> _CollectDiscoveryOutput:
    """Collect all skill roots, discovered names, and warnings."""
    overrides, warnings = load_source_overrides(
        repo_root=repo_root,
        env=options["env"],
        active_skill_names=options["active_skills"],
        strict_skill_names=options["strict_skills"],
        user_override_path=options["user_override_path"],
        repo_override_path=options["repo_override_path"],
    )
    roots = resolve_skill_roots(
        repo_root,
        extra_roots=options["extra_roots"],
        foreign_roots=options["foreign_roots"],
        env=options["env"],
    )
    usable_skills = _discover_skills(roots["usable_roots"])
    advisory_skills = _discover_skills(roots["advisory_roots"])
    unreferenced_skills = sorted(set(usable_skills) - set(manifest["skills"]))
    merged_skills = _build_merged_skills(
        options["active_skills"],
        manifest,
        overrides,
        usable_skills,
        advisory_skills,
    )
    return {
        "warnings": warnings,
        "roots": roots,
        "merged_skills": merged_skills,
        "unreferenced_skills": unreferenced_skills,
    }


def _bootstrap_report_payload(context: _ReportPayloadContext) -> dict[str, Any]:
    """Build the final bootstrap report payload."""
    summary = _build_summary(
        context["lanes"],
        context["active_lanes"],
        context["install_candidates"],
        context["strict_skills"],
    )
    return {
        "repo_root": str(context["repo_root"]),
        "artifact_root": str(context["out_dir"] / "bootstrap"),
        "repo_profile": context["profile"],
        "roots": context["roots"],
        "skills": context["merged_skills"],
        "lanes": context["lanes"],
        "install_candidates": context["install_candidates"],
        "unreferenced_skills": context["unreferenced_skills"],
        "summary": summary,
        "warnings": sorted(set(context["warnings"])),
    }


def _evaluate_lanes(
    active_lanes: list[str],
    profile: dict[str, Any],
    manifest: dict[str, Any],
    merged_skills: dict[str, dict[str, Any]],
    warnings: list[str],
) -> dict[str, dict[str, Any]]:
    """Evaluate all active lanes and fold lane warnings."""
    lanes: dict[str, dict[str, Any]] = {}
    for lane_name in active_lanes:
        lane = _evaluate_lane(
            lane_name,
            manifest["lanes"][lane_name],
            merged_skills,
            profile,
        )
        lanes[lane_name] = lane
        warnings.extend(lane["warnings"])
    return lanes


def _collect_skill_warnings(merged_skills: dict[str, Any], warnings: list[str]) -> None:
    """Append warnings from merged skill descriptors."""
    for skill in merged_skills.values():
        if "warnings" in skill:
            warnings.extend(skill["warnings"])


def _build_summary(
    lanes: dict[str, dict[str, Any]],
    active_lanes: list[str],
    install_candidates: list[dict[str, Any]],
    strict_skills: set[str],
) -> dict[str, Any]:
    """Build summary fields for the bootstrap report."""
    stop_before_discovery = any(lane["blocking"] for lane in lanes.values())
    restart_required = any(
        item["restart_required"]
        for item in install_candidates
        if item["post_install_state"] == "available_next_run"
        and item["name"] in strict_skills
    )
    return {
        "stop_before_discovery": stop_before_discovery,
        "restart_required": restart_required,
        "active_lanes": active_lanes,
    }


def _build_bootstrap_report_payload(
    repo_root: Path,
    manifest: dict[str, Any],
    out_dir: Path,
    profile: dict[str, Any],
    options: _BuildBootstrapOptions,
) -> dict[str, Any]:
    """Build the core bootstrap report payload."""
    active_lanes, active_skills, strict_skills = _collect_active_skills(
        profile, manifest, options["required_skill_names"]
    )
    discovery = _collect_discovery_inputs(
        repo_root,
        manifest,
        {
            "env": options["env"],
            "active_skills": active_skills,
            "strict_skills": strict_skills,
            "user_override_path": options["user_override_path"],
            "repo_override_path": options["repo_override_path"],
            "extra_roots": options["extra_roots"],
            "foreign_roots": options["foreign_roots"],
        },
    )
    lanes = _evaluate_lanes(
        active_lanes,
        profile,
        manifest,
        discovery["merged_skills"],
        discovery["warnings"],
    )
    _collect_skill_warnings(discovery["merged_skills"], discovery["warnings"])
    _mark_blocking_skills(lanes, manifest, discovery["merged_skills"])
    install_candidates = _build_install_candidates(discovery["merged_skills"])
    return _bootstrap_report_payload(
        {
            "repo_root": repo_root,
            "out_dir": out_dir,
            "profile": profile,
            "active_lanes": active_lanes,
            "strict_skills": strict_skills,
            "roots": discovery["roots"],
            "warnings": discovery["warnings"],
            "merged_skills": discovery["merged_skills"],
            "lanes": lanes,
            "install_candidates": install_candidates,
            "unreferenced_skills": discovery["unreferenced_skills"],
        }
    )


def build_bootstrap_report(
    request: BootstrapReportRequest | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build the full bootstrap report for a repository."""
    request = _coerce_bootstrap_report_request(request, kwargs)
    repo_root = _normalize_repo_root(request.repo_root)
    manifest = load_dependency_manifest(request.manifest_path)
    return _build_bootstrap_report_payload(
        repo_root,
        manifest,
        request.out_dir.resolve(),
        scan_repo_profile(repo_root),
        {
            "env": request.env,
            "extra_roots": request.extra_roots,
            "foreign_roots": request.foreign_roots,
            "user_override_path": request.user_override_path,
            "repo_override_path": request.repo_override_path,
            "required_skill_names": request.required_skill_names,
        },
    )


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
    lines.extend(
        f"- `{skill_name}`: `{skill['state']}`"
        for skill_name, skill in report["skills"].items()
    )
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    if report.get("unreferenced_skills"):
        lines.extend(["", "## Unreferenced Skills (advisory)", ""])
        lines.extend(f"- `{name}`" for name in report["unreferenced_skills"])
    lines.append("")
    return "\n".join(lines)


def _markdown_install_plan(report: dict[str, Any]) -> str:
    lines = [
        "# Install Plan",
        "",
        "This checker never installs skills. Use the commands below "
        "only after explicit approval.",
        "",
        "Replace `{dest}` with your skills root "
        "(default: `~/.agents/skills`).",
        "",
    ]
    if not report["install_candidates"]:
        lines.append("No install candidates were detected.")
        lines.append("")
        return "\n".join(lines)
    # ... existing per-candidate loop unchanged ...

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
