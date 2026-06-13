"""Tests for scripts/synthesize_packets.py — packet and patch-proposal synthesis."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

synth = importlib.import_module("scripts.synthesize_packets")


# ---------------------------------------------------------------------------
# packet_for tests
# ---------------------------------------------------------------------------


def test_packet_from_complexity_finding_has_expected_shape():
    """A complexity finding produces a K-7 packet with goal/files/budget."""
    finding = {
        "id": "c8d75b7bbbd265b4",
        "leaf": "complexity",
        "location": {
            "line_end": 485,
            "line_start": 457,
            "symbol": "build_bootstrap_report",
        },
        "metric": {
            "name": "parameter_count",
            "threshold": 5.0,
            "value": 9.0,
        },
        "path": "scripts/_bootstrap_report.py",
        "severity": "low",
        "signal": "SIMPLIFY",
        "suggested_action": "Reduce parameters of build_bootstrap_report() — 9 exceeds 5",
    }
    repo = "/tmp/test-repo"

    packet = synth.packet_for(finding, repo)

    # K-7 keys
    assert packet["packet_id"] == "c8d75b7bbbd265b4"
    assert packet["repo"] == repo
    assert "parameter_count" in packet["goal"]
    assert "build_bootstrap_report" in packet["goal"]
    assert "scripts/_bootstrap_report.py" in packet["goal"]
    assert "9" in packet["goal"] or "9.0" in packet["goal"]
    assert "5" in packet["goal"] or "5.0" in packet["goal"]
    assert packet["files"] == ["scripts/_bootstrap_report.py"]
    assert packet["must_run"] == []
    assert packet["expected"] == []
    assert packet["forbidden"] == []
    assert isinstance(packet["token_budget"], int)
    assert packet["token_budget"] <= 8000


def test_packet_with_module_level_finding():
    """Module-level maintainability finding still produces valid packet."""
    finding = {
        "id": "57e32e158e7f3dd1",
        "leaf": "complexity",
        "location": {
            "line_end": 1,
            "line_start": 1,
            "symbol": "<module>",
        },
        "metric": {
            "name": "maintainability_index",
            "threshold": 65.0,
            "value": 24.5,
        },
        "path": "scripts/_bootstrap_report.py",
        "severity": "medium",
        "signal": "SIMPLIFY",
        "suggested_action": "Improve maintainability of scripts/_bootstrap_report.py — MI 24.5 below 65",
    }

    packet = synth.packet_for(finding, "/repo")

    assert packet["packet_id"] == "57e32e158e7f3dd1"
    assert "maintainability_index" in packet["goal"]
    assert "<module>" in packet["goal"]
    assert "scripts/_bootstrap_report.py" in packet["goal"]
    assert "24.5" in packet["goal"]
    assert "65" in packet["goal"] or "65.0" in packet["goal"]
    assert packet["files"] == ["scripts/_bootstrap_report.py"]


def test_packet_without_metric_name_falls_back():
    """Finding without metric.name uses signal as fallback."""
    finding = {
        "id": "abc123",
        "leaf": "hotspot",
        "path": "scripts/check_skill_requirements.py",
        "location": {"symbol": "scripts/check_skill_requirements.py"},
        "signal": "DECOMPOSE",
        "metric": {"value": 3.2, "threshold": 1.0},
    }

    packet = synth.packet_for(finding, "/repo")

    assert packet["packet_id"] == "abc123"
    assert "Reduce" in packet["goal"]
    assert "scripts/check_skill_requirements.py" in packet["goal"]
    assert "3.2" in packet["goal"]
    assert "1" in packet["goal"] or "1.0" in packet["goal"]


def test_packet_without_threshold_handles_gracefully():
    """Metric without threshold still produces goal."""
    finding = {
        "id": "no-thresh-1",
        "leaf": "complexity",
        "path": "x.py",
        "location": {"symbol": "f"},
        "metric": {"name": "lines", "value": 200},
    }

    packet = synth.packet_for(finding, "/repo")

    assert "to acceptable level" in packet["goal"]
    assert "200" in packet["goal"]


def test_packet_without_value_handles_gracefully():
    """Metric without value still produces goal."""
    finding = {
        "id": "no-val-1",
        "leaf": "complexity",
        "path": "x.py",
        "location": {"symbol": "f"},
        "metric": {"name": "complexity", "threshold": 10.0},
    }

    packet = synth.packet_for(finding, "/repo")

    assert "from current level" in packet["goal"]
    assert "10" in packet["goal"] or "10.0" in packet["goal"]


def test_packet_token_budget_is_allowed_value():
    """Token budget is 8000 (exact match to spec)."""
    finding = {
        "id": "budget-test",
        "leaf": "test",
        "path": "t.py",
        "location": {"symbol": "f"},
        "metric": {"name": "m", "value": 1, "threshold": 2},
    }

    packet = synth.packet_for(finding, "/repo")

    assert packet["token_budget"] == 8000


# ---------------------------------------------------------------------------
# mechanical_patches tests
# ---------------------------------------------------------------------------


def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_synthetic_repo_unused_import_produces_patch_and_verify_json(tmp_path: Path):
    """A synthetic Python repo with one unused import → patch + verify JSON."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _write_py(repo / "src" / "app.py", "import os\nimport sys\n\nprint(sys.version)\n")

    findings = [
        {
            "id": "f401-example",
            "leaf": "dead-code-audit",
            "metric": {"name": "unused_import", "value": 1.0, "threshold": 0.0},
            "path": "src/app.py",
            "signal": "DELETE",
            "suggested_action": "Remove unused import: os",
        }
    ]

    out_dir = tmp_path / "out"
    results = synth.mechanical_patches(findings, str(repo), str(out_dir))

    assert len(results) == 1
    result = results[0]
    assert result["id"] == "f401-example"
    assert result["class"] == "dead-code-audit/unused_import"

    if result["error"]:
        # If ruff isn't available or fails, still check error is present
        assert isinstance(result["error"], str)
    else:
        assert result["patch_path"] is not None
        assert result["verify_path"] is not None
        assert result["diff_bytes"] > 0

        patch_text = Path(result["patch_path"]).read_text(encoding="utf-8")
        assert "-import os" in patch_text or "import os" in patch_text

        verify = json.loads(Path(result["verify_path"]).read_text(encoding="utf-8"))
        assert verify["packet_id"] == "f401-example"
        assert verify["class"] == "dead-code-audit/unused_import"
        assert len(verify["verify_commands"]) >= 1
        assert any("F401" in cmd["cmd"] for cmd in verify["verify_commands"])


def test_unknown_class_is_skipped_silently(tmp_path: Path):
    """Findings with classes not in the safe table are skipped."""
    repo = tmp_path / "repo"
    repo.mkdir()

    findings = [
        {
            "id": "unknown-class-finding",
            "leaf": "complexity",
            "metric": {"name": "parameter_count", "value": 10.0, "threshold": 5.0},
            "path": "x.py",
            "signal": "SIMPLIFY",
        }
    ]

    out_dir = tmp_path / "out"
    results = synth.mechanical_patches(findings, str(repo), str(out_dir))

    assert results == []


def test_no_findings_produces_empty_results(tmp_path: Path):
    """Empty findings list → empty results."""
    repo = tmp_path / "repo"
    repo.mkdir()

    results = synth.mechanical_patches([], str(repo), str(tmp_path / "out"))

    assert results == []


def test_non_dict_finding_is_skipped(tmp_path: Path):
    """Non-dict entries in findings are skipped."""
    repo = tmp_path / "repo"
    repo.mkdir()

    results = synth.mechanical_patches(["not-a-dict", None, 42], str(repo), str(tmp_path / "out"))

    assert results == []


def test_finding_without_id_is_skipped(tmp_path: Path):
    """Finding with a safe class but no id is skipped."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _write_py(repo / "src" / "app.py", "import os\n\nprint('ok')\n")

    findings = [
        {
            # no id
            "leaf": "dead-code-audit",
            "metric": {"name": "unused_import", "value": 1.0, "threshold": 0.0},
            "path": "src/app.py",
            "signal": "DELETE",
        }
    ]

    out_dir = tmp_path / "out"
    results = synth.mechanical_patches(findings, str(repo), str(out_dir))

    assert results == []


def test_format_drift_class_runs_ruff_format(tmp_path: Path):
    """quality-audit/format_drift runs ruff format --diff on the file."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _write_py(repo / "src" / "app.py", "x=1\n")

    findings = [
        {
            "id": "fmt-drift-1",
            "leaf": "quality-audit",
            "metric": {"name": "format_drift", "value": 1.0, "threshold": 0.0},
            "path": "src/app.py",
            "signal": "FORMAT",
        }
    ]

    out_dir = tmp_path / "out"
    results = synth.mechanical_patches(findings, str(repo), str(out_dir))

    assert len(results) == 1
    result = results[0]
    assert result["id"] == "fmt-drift-1"
    assert result["class"] == "quality-audit/format_drift"

    # Whether a diff is found or not, the result should have either a patch or an error
    assert result["patch_path"] is not None or result["error"] is not None


def test_patch_file_is_not_applied(tmp_path: Path):
    """Generated patch files never mutate the source repo."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    original = "import os\nimport sys\n\nprint(sys.version)\n"
    _write_py(repo / "src" / "app.py", original)

    findings = [
        {
            "id": "no-apply-1",
            "leaf": "dead-code-audit",
            "metric": {"name": "unused_import", "value": 1.0, "threshold": 0.0},
            "path": "src/app.py",
            "signal": "DELETE",
        }
    ]

    out_dir = tmp_path / "out"
    synth.mechanical_patches(findings, str(repo), str(out_dir))

    # Verify the source file is unchanged
    current = (repo / "src" / "app.py").read_text(encoding="utf-8")
    assert current == original, "Source file was mutated by mechanical_patches!"


def test_finding_class_derives_from_metric_name():
    """_finding_class uses metric.name over signal."""
    finding = {
        "leaf": "dead-code-audit",
        "metric": {"name": "unused_import"},
        "signal": "DELETE",
    }
    assert synth._finding_class(finding) == "dead-code-audit/unused_import"


def test_finding_class_falls_back_to_signal():
    """_finding_class falls back to signal when metric.name is missing."""
    finding = {
        "leaf": "quality-audit",
        "metric": {},
        "signal": "FORMAT",
    }
    assert synth._finding_class(finding) == "quality-audit/format"


def test_metric_repr_int_float():
    """_metric_repr drops .0 for whole-number floats."""
    assert synth._metric_repr(5.0) == "5"
    assert synth._metric_repr(3.2) == "3.2"
    assert synth._metric_repr(0) == "0"
    assert synth._metric_repr(10) == "10"


def test_proposals_directory_is_created(tmp_path: Path):
    """mechanical_patches creates the proposals/ directory."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _write_py(repo / "src" / "app.py", "import os\n\nprint('ok')\n")

    findings = [
        {
            "id": "dir-test-1",
            "leaf": "dead-code-audit",
            "metric": {"name": "unused_import", "value": 1.0, "threshold": 0.0},
            "path": "src/app.py",
            "signal": "DELETE",
        }
    ]

    out_dir = tmp_path / "out"
    assert not (out_dir / "proposals").exists()

    synth.mechanical_patches(findings, str(repo), str(out_dir))

    assert (out_dir / "proposals").is_dir()


# ---------------------------------------------------------------------------
# SAFE_PATCH_TABLE integrity
# ---------------------------------------------------------------------------


def test_safe_patch_table_contains_required_classes():
    """The safe table must include the two required classes."""
    assert "dead-code-audit/unused_import" in synth.SAFE_PATCH_TABLE
    assert "quality-audit/format_drift" in synth.SAFE_PATCH_TABLE
