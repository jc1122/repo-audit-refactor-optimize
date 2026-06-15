from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TypedDict

from scripts._skill_probe import (
    _REQUIRED_SKILL_FIELDS,
    _install_command_for_skill,
    _skill_entry,
)


CONFIG_DIR_NAME = "repo-audit-refactor-optimize"
DEFAULT_REPO_OVERRIDE = ".repo-audit-refactor-optimize/skill-sources.json"
KNOWN_LANGUAGES = frozenset({"python", "c", "rust", "assembly"})
KNOWN_TEST_SYSTEMS = frozenset({"pytest", "cargo", "cmake", "meson", "make"})


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
    base = Path(config_home).expanduser() if config_home else _home_dir(env) / ".config"
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


class SourceOverrideRequest(TypedDict, total=True):
    repo_root: Path
    env: dict[str, str] | None
    active_skill_names: set[str]
    strict_skill_names: set[str]
    user_override_path: Path | None
    repo_override_path: Path | None


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
    if (
        not isinstance(payload, dict)
        or "skills" not in payload
        or "lanes" not in payload
    ):
        raise ValueError(f"Invalid dependency manifest: {manifest_path}")
    for name, entry in payload["skills"].items():
        missing = _REQUIRED_SKILL_FIELDS - entry.keys()
        if missing:
            raise ValueError(
                f"Skill '{name}' missing required fields in manifest: {missing}"
            )
    return payload


# Fields an override file may set. `install_source` is deliberately NOT here:
# a git install command is built only from the trusted manifest `sources` map, so
# an audited (untrusted) repo override cannot inject an arbitrary clone/install.
_OVERRIDE_SCHEMA: dict[str, type] = {
    "source_type": str,
    "manual_fallback": str,
    "restart_required_if_installed": bool,
}


def _is_skill_override_valid(payload: dict[str, Any]) -> bool:
    return all(
        payload.get(field) is None or isinstance(payload[field], expected_type)
        for field, expected_type in _OVERRIDE_SCHEMA.items()
    )


def _whitelisted_override(entry: dict[str, Any]) -> dict[str, Any]:
    """Keep only schema-known keys so an override cannot inject `source`,
    `install_source`, or any other unexpected field."""
    return {k: v for k, v in entry.items() if k in _OVERRIDE_SCHEMA}


def _read_override_payload(scope: str, path: Path) -> dict[str, Any]:
    """Read and validate the ``"skills"`` map from a single source override file.

    Returns an empty dict when *path* does not exist so the caller can skip
    the source without additional branches.
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed {scope} override file: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("skills"), dict):
        raise ValueError(f"Invalid {scope} override file: {path}")
    return payload["skills"]


def load_source_overrides(
    request: SourceOverrideRequest | None = None,
    **kwargs: Any,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    values: dict[str, Any] = dict(request or {}, **kwargs)
    repo_root = values["repo_root"]
    env = values["env"]
    active_skill_names = values["active_skill_names"]
    strict_skill_names = values["strict_skill_names"]
    user_override_path = values.get("user_override_path")
    repo_override_path = values.get("repo_override_path")
    warnings: list[str] = []
    merged: dict[str, dict[str, Any]] = {}
    sources = (
        ("user", user_override_path or _default_user_override_path(env)),
        ("repo", repo_override_path or (repo_root / DEFAULT_REPO_OVERRIDE)),
    )

    for scope, path in sources:
        skills = _read_override_payload(scope, path)
        for skill_name, entry in skills.items():
            if not isinstance(entry, dict) or not _is_skill_override_valid(entry):
                if skill_name in strict_skill_names:
                    raise ValueError(
                        f"Invalid override entry for required skill: {skill_name}"
                    )
                warnings.append(f"Ignored invalid override entry for {skill_name}.")
                continue
            if skill_name not in active_skill_names:
                warnings.append(
                    f"Ignored override for unknown or inactive skill {skill_name}."
                )
                continue
            merged[skill_name] = _whitelisted_override(entry)

    return merged, warnings


def _matches_when(profile: dict[str, Any], conditions: dict[str, Any]) -> bool:
    """Return True when the repo profile satisfies all lane activation conditions."""
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
        else:
            # Treat as a benchmark-surface condition by default (fail-closed).
            if bool(expected) != (key in benchmarks):
                return False
    return True


def _relevant_lane_names(
    profile: dict[str, Any], manifest: dict[str, Any]
) -> list[str]:
    lane_names: list[str] = [
        name
        for name, lane in manifest["lanes"].items()
        if lane.get("always") or _matches_when(profile, lane.get("when", {}))
    ]
    return lane_names


def _all_usable(names: list[str], skills: dict[str, dict[str, Any]]) -> bool:
    return all(skills[name]["state"] == "usable_now" for name in names)


def _usable_optionals(
    lane: dict[str, Any], skills: dict[str, dict[str, Any]]
) -> list[str]:
    return [
        name
        for name in lane.get("optional", [])
        if skills[name]["state"] == "usable_now"
    ]


def _evaluate_preferred_fallback_lane(
    lane: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    fallback_warning: str,
) -> tuple[str, list[str], list[str]]:
    preferred = lane.get("preferred", [])
    fallback = lane.get("fallback", [])
    warnings: list[str] = []
    if preferred and _all_usable(preferred, skills):
        selected = list(preferred) + _usable_optionals(lane, skills)
        return "full", selected, warnings
    if fallback and _all_usable(fallback, skills):
        warnings.append(fallback_warning)
        selected = list(fallback) + _usable_optionals(lane, skills)
        return "degraded", selected, warnings
    return "manual", [], warnings


def _evaluate_test_lane(
    lane: dict[str, Any], skills: dict[str, dict[str, Any]]
) -> tuple[str, list[str], list[str]]:
    return _evaluate_preferred_fallback_lane(
        lane, skills, "Preferred test audit skill unavailable; using fallback pair."
    )


def _evaluate_code_health_lane(
    lane: dict[str, Any], skills: dict[str, dict[str, Any]]
) -> tuple[str, list[str], list[str]]:
    return _evaluate_preferred_fallback_lane(
        lane,
        skills,
        "Preferred code-health umbrella unavailable; using leaf audits directly.",
    )


def _evaluate_coverage_lane(
    lane: dict[str, Any], skills: dict[str, dict[str, Any]]
) -> tuple[str, list[str], list[str]]:
    return _evaluate_preferred_fallback_lane(
        lane, skills, "Preferred coverage skill unavailable; using fallback."
    )


def _evaluate_performance_lane(
    lane: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    if not profile["has_deterministic_perf_surface"]:
        if profile["has_deterministic_test_surface"]:
            if _all_usable(lane.get("preferred", []), skills):
                warnings.append(
                    "No benchmark surface; agent may synthesize one "
                    "(perf-benchmark usable)."
                )
                selected = list(lane.get("preferred", []))
                selected.extend(_usable_optionals(lane, skills))
                return "synthesizable", selected, warnings
            warnings.append(
                "No benchmark surface detected; performance work remains manual."
            )
            return "manual", [], warnings
        return "blocked", [], warnings

    if _all_usable(lane.get("preferred", []), skills):
        selected = list(lane.get("preferred", []))
        fallback = lane.get("fallback", [])
        if not fallback:
            selected.extend(_usable_optionals(lane, skills))
            return "full", selected, warnings
        if _all_usable(fallback, skills):
            selected.extend(fallback)
            selected.extend(_usable_optionals(lane, skills))
            return "full", selected, warnings
        warnings.append("Optimization skill missing; lane remains benchmark-first.")
        return "degraded", selected, warnings

    return "manual", [], warnings


def _evaluate_bootstrap_lane(
    lane: dict[str, Any], skills: dict[str, dict[str, Any]]
) -> tuple[str, list[str], list[str]]:
    if _all_usable(lane.get("preferred", []), skills):
        return "full", list(lane.get("preferred", [])), []
    return (
        "degraded",
        [],
        ["Bootstrap helper skills unavailable; raw Skills CLI fallback required."],
    )


def _evaluate_orchestration_lane(
    lane: dict[str, Any], skills: dict[str, dict[str, Any]]
) -> tuple[str, list[str], list[str]]:
    if _all_usable(lane.get("preferred", []), skills):
        selected = list(lane.get("preferred", [])) + _usable_optionals(lane, skills)
        return "full", selected, []
    return "manual", [], []


_LANE_EVALUATORS = {
    "test": lambda lane, skills, profile: _evaluate_test_lane(lane, skills),
    "code_health": lambda lane, skills, profile: _evaluate_code_health_lane(
        lane, skills
    ),
    "coverage": lambda lane, skills, profile: _evaluate_coverage_lane(lane, skills),
    "audit": lambda lane, skills, profile: _evaluate_preferred_fallback_lane(
        lane, skills, "Preferred audit skill unavailable; using fallback."
    ),
    "performance": _evaluate_performance_lane,
    "bootstrap": lambda lane, skills, profile: _evaluate_bootstrap_lane(lane, skills),
    "orchestration": lambda lane, skills, profile: _evaluate_orchestration_lane(
        lane, skills
    ),
}


def _evaluate_lane(
    lane_name: str,
    lane: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    lane_type = lane["lane_type"]
    if lane_type not in _LANE_EVALUATORS:
        warnings_list = [
            f"Unknown lane type '{lane_type}'; using orchestration evaluator."
        ]
    else:
        warnings_list = []
    evaluator = _LANE_EVALUATORS.get(lane_type, _LANE_EVALUATORS["orchestration"])
    state, selected, eval_warnings = evaluator(lane, skills, profile)
    warnings = warnings_list + eval_warnings

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
    for name in required_skill_names or []:
        if name not in manifest["skills"]:
            raise ValueError(f"Required skill '{name}' is not defined in the manifest.")
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


def _resolve_skill_source(
    skill_config: dict[str, Any], sources: dict[str, Any]
) -> None:
    """Attach a git install_source from the shared `sources` map (DRY).

    No-op if the skill has no `source`, already has an explicit install_source,
    or the referenced source is missing/not a git source.
    """
    src_id = skill_config.get("source")
    if not src_id or skill_config.get("install_source"):
        return
    src = sources.get(src_id)
    if not isinstance(src, dict) or src.get("kind") != "git":
        return
    skill_config["install_source"] = {
        "method": "git",
        "url": src.get("url"),
        "tag": src.get("tag"),
        "install": src.get("install"),
    }


def _build_merged_skills(
    active_skills: set[str],
    manifest: dict[str, Any],
    overrides: dict[str, dict[str, Any]],
    usable_skills: dict[str, dict[str, Any]],
    advisory_skills: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    sources = manifest.get("sources", {})
    merged: dict[str, dict[str, Any]] = {}
    for skill_name in sorted(active_skills):
        skill_config = dict(manifest["skills"][skill_name])
        if skill_name in overrides:
            skill_config.update(overrides[skill_name])
        _resolve_skill_source(skill_config, sources)
        merged[skill_name] = _skill_entry(
            skill_name, skill_config, usable_skills, advisory_skills
        )
    return merged


def _build_install_candidates(
    merged_skills: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    by_source: dict[str, dict[str, Any]] = {}
    for skill_name, skill in merged_skills.items():
        if skill["state"] != "installable_now":
            continue
        command = _install_command_for_skill(skill)
        if not command:
            continue
        source = skill.get("source")
        if source:  # git source: one command installs all its skills -> dedupe
            existing = by_source.get(source)
            if existing is not None:
                existing["covers"].append(skill_name)  # record every skill covered
                continue
            candidate = {
                "name": source,
                "command": command,
                "covers": [skill_name],
                "post_install_state": skill.get("post_install_state"),
                "restart_required": skill["restart_required_if_installed"],
                "source_type": skill["source_type"],
            }
            by_source[source] = candidate
            candidates.append(candidate)
        else:  # public skills_cli: per-skill (unchanged)
            candidates.append({
                "name": skill_name,
                "command": command,
                "covers": [skill_name],
                "post_install_state": skill.get("post_install_state"),
                "restart_required": skill["restart_required_if_installed"],
                "source_type": skill["source_type"],
            })
    return candidates


def _mark_blocking_skills(
    lanes: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
    merged_skills: dict[str, dict[str, Any]],
) -> None:
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
