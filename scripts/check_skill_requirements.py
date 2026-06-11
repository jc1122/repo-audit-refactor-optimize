from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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

try:
    from scripts._bootstrap_report import (
        SKIP_DIRS,
        _BENCH_NAME_KW,
        _BENCH_PATH_KW,
        _BENCH_SURFACE,
        _LANG_MAP,
        _benchmark_surface,
        _classify_file_full,
        _dir_marker_contributions,
        _has_any_keyword,
        _has_any_suffix_py,
        _is_python_test_dir,
        _markdown_install_plan,
        _markdown_report,
        _ordered_list,
        _path_parts_lower,
        _pyproject_contributions,
        build_bootstrap_report,
        scan_repo_profile,
        write_bootstrap_outputs,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts._bootstrap_report import (
        SKIP_DIRS,
        _BENCH_NAME_KW,
        _BENCH_PATH_KW,
        _BENCH_SURFACE,
        _LANG_MAP,
        _benchmark_surface,
        _classify_file_full,
        _dir_marker_contributions,
        _has_any_keyword,
        _has_any_suffix_py,
        _is_python_test_dir,
        _markdown_install_plan,
        _markdown_report,
        _ordered_list,
        _path_parts_lower,
        _pyproject_contributions,
        build_bootstrap_report,
        scan_repo_profile,
        write_bootstrap_outputs,
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
