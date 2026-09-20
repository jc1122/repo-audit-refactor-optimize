"""The public skill entrypoint must stay thin, portable, and honest.

Guards the proposal findings: Agent Skills frontmatter (no top-level version),
bounded body length, no hardcoded host paths, and none of the retired false
guarantees (always-available process skills, conflict-free merges).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

cr = importlib.import_module("scripts.check_release")


def _skill_text() -> str:
    return (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_frontmatter_uses_metadata_version():
    meta = cr.frontmatter(REPO_ROOT / "SKILL.md")
    assert meta.get("name") == "repo-audit-refactor-optimize"
    assert "version" not in meta, "top-level 'version:' retired; use metadata.version"
    metadata = meta.get("metadata")
    assert isinstance(metadata, dict) and metadata.get("version") == "1.0.0"
    requires = metadata.get("requires")
    assert isinstance(requires, str), "metadata values must be plain strings"
    name, op, floor = requires.split()
    assert (name, op, floor) == ("repo-audit-checks", ">=", "1.0.0")
    assert (meta.get("description") or "").strip(), "description must be non-empty"


def test_preset_example_names_real_preset():
    import re
    presets = set(re.findall(r"--preset\s+(\S+)", _skill_text()))
    assert presets, "SKILL.md shows no --preset example"
    assert presets <= {"code-health", "test"}, f"unknown preset in SKILL.md: {presets}"


def test_body_line_count_within_editorial_target():
    text = _skill_text()
    body = text[text.index("---", 3) + 3:]
    lines = [ln for ln in body.strip().splitlines()]
    assert 80 <= len(lines) <= 120, f"skill body is {len(lines)} lines, target 80-120"


def test_no_hardcoded_host_paths():
    text = _skill_text()
    for banned in ("~/.claude", "~/.codex", "CODEX_HOME", ".claude/skills"):
        assert banned not in text, f"SKILL.md hardcodes host path: {banned}"


def test_no_retired_guarantees():
    text = _skill_text()
    for banned in (
        "always_available",
        "always-available",
        "harness-guaranteed",
        "conflict-free by construction",
        "mprr",
        "MPRR",
    ):
        assert banned not in text, f"SKILL.md carries retired guarantee: {banned}"


def test_declares_core_dependency_and_scope_rule():
    text = _skill_text()
    assert "repo-audit" in text and "1.0.0" in text
    assert "audit" in text.lower() and "authoriz" in text.lower()
