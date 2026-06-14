"""Synthesize worker packets and mechanical patch proposals from wave findings.

Advisory only — never applies generated patches.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# K-7 worker packet shape
# ---------------------------------------------------------------------------


def packet_for(finding: dict[str, Any], repo: str) -> dict[str, Any]:
    """Build a K-7 worker packet for a single wave finding.

    The returned dict contains:
      packet_id      — from the finding id
      repo           — repository root path
      goal           — natural-language remediation goal
      files          — list of affected paths
      must_run       — list of verification commands required before close
      expected       — list of expected verification outcomes
      forbidden       — list of forbidden regression signals
      token_budget   — max token budget (<= 8000)
    """
    finding_id = str(finding.get("id", ""))
    location = finding.get("location", {}) or {}
    metric = finding.get("metric", {}) or {}
    symbol = location.get("symbol", "") or str(finding.get("symbol", ""))
    path_val = str(finding.get("path", ""))

    # Derive metric name: nested metric dict takes priority
    if isinstance(metric, dict):
        metric_name = str(metric.get("name", ""))
        metric_value = metric.get("value")
        metric_threshold = metric.get("threshold")
    else:
        metric_name = str(finding.get("signal", metric))
        metric_value = None
        metric_threshold = None

    # Build goal with human-readable placeholders
    if metric_value is not None:
        from_phrase = f"from {_metric_repr(metric_value)}"
    else:
        from_phrase = "from current level"
    if metric_threshold is not None:
        to_phrase = f"to <= {_metric_repr(metric_threshold)}"
    else:
        to_phrase = "to acceptable level"

    goal = f"Reduce {metric_name} of {symbol} in {path_val} {from_phrase} {to_phrase}"

    return {
        "packet_id": finding_id,
        "repo": repo,
        "goal": goal,
        "files": [path_val],
        "must_run": [],
        "expected": [],
        "forbidden": [],
        "token_budget": 8000,  # nosec B105
    }


# ---------------------------------------------------------------------------
# Safe mechanical patch mapping
# ---------------------------------------------------------------------------


def _finding_class(finding: dict[str, Any]) -> str:
    """Derive a safe-table class key from a finding."""
    leaf = str(finding.get("leaf", ""))
    metric = finding.get("metric", {})
    if isinstance(metric, dict):
        classifier = str(metric.get("name", ""))
        if not classifier:
            classifier = str(finding.get("signal", ""))
    else:
        classifier = str(finding.get("signal", ""))
    if leaf and classifier:
        return f"{leaf}/{classifier.lower()}"
    return ""


def _metric_repr(value: Any) -> str:
    """Format a metric value, dropping .0 for whole-number floats."""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


SAFE_PATCH_TABLE: dict[str, dict[str, Any]] = {
    "dead-code-audit/unused_import": {
        "tool": "ruff",
        "check_cmd": ["check", "--select", "F401", "--diff"],
        "verify_cmd": ["ruff", "check", "--select", "F401"],
        "verify_expect": "No unused import violations remaining.",
    },
    "quality-audit/format_drift": {
        "tool": "ruff",
        "check_cmd": ["format", "--diff"],
        "verify_cmd": ["ruff", "format", "--check"],
        "verify_expect": "Format check passes (no drift).",
    },
}


def _run_ruff(
    repo: str, file_path: str, check_cmd: list[str]
) -> tuple[str, str | None]:
    """Run ruff against *file_path* inside *repo* and return (stdout, error)."""
    full_cmd = ["ruff"] + check_cmd + [file_path]
    try:
        result = subprocess.run(  # nosec B603
            full_cmd,
            capture_output=True,
            text=True,
            cwd=repo,
            timeout=30,
            shell=False,
        )
        if result.returncode != 0:
            return result.stdout, (
                result.stderr or f"ruff exited with code {result.returncode}"
            )
        return result.stdout, None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return "", str(exc)


# ---------------------------------------------------------------------------
# Two-tier lessons ledger: capped scope-matched injection + escalation
# ---------------------------------------------------------------------------


def inject_lessons(
    packet: dict[str, Any],
    lessons: list[dict[str, Any]],
    cap: int,
) -> dict[str, Any]:
    """Inject capped, scope-matched *binding* lessons into a worker packet.

    Selects lessons whose ``tier`` is ``"binding"`` and whose ``scope`` matches
    ``packet["scope"]``, sorts the selection by ``fires`` descending (a missing
    ``fires`` counts as 0, stable for ties), truncates to ``cap`` entries, and
    attaches them under the new ``packet["lessons"]`` key as a list of
    ``{"id", "text", "command"}`` dicts. The ``cap`` bounds the injected text so
    the L-7 8k-token packet budget holds. Mutates *packet* in place and returns
    it.
    """
    scope = packet.get("scope")
    selected = [
        lesson
        for lesson in lessons
        if lesson.get("tier") == "binding" and lesson.get("scope") == scope
    ]
    selected.sort(key=lambda lesson: lesson.get("fires", 0), reverse=True)
    selected = selected[:cap]
    packet["lessons"] = [
        {
            "id": lesson.get("id"),
            "text": lesson.get("text", ""),
            "command": lesson.get("command", ""),
        }
        for lesson in selected
    ]
    return packet


def needs_automation(lesson: dict[str, Any]) -> bool:
    """Return True when a binding lesson has fired enough to warrant automation.

    A lesson needs automation when it is ``binding``, has fired at least three
    times, and has not already been ``escalated``.
    """
    return (
        lesson.get("tier") == "binding"
        and lesson.get("fires", 0) >= 3
        and not lesson.get("escalated", False)
    )


def mechanical_patches(
    findings: list[dict[str, Any]],
    repo: str,
    out_dir: str,
) -> list[dict[str, Any]]:
    """Generate safe mechanical patches for eligible findings.

    For each finding whose ``{leaf}/{metric.name}`` key appears in
    ``SAFE_PATCH_TABLE``, this function:

    1.  Runs the configured ruff check command against the target file in the
        repo root, capturing a unified diff *without* applying it.
    2.  Writes the diff to ``<out_dir>/proposals/<id>.patch``.
    3.  Writes a verify JSON to ``<out_dir>/proposals/<id>.verify.json`` with
        the ruff verify command and an expected outcome string.

    Unknown classes are skipped silently.
    Returns a list of proposal records.
    """
    repo_path = Path(repo).resolve()
    out_path = Path(out_dir).resolve()
    proposals_dir = out_path / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    for finding in findings:
        # Skip non-dict entries
        if not isinstance(finding, dict):
            continue

        # Skip findings without an id
        if "id" not in finding:
            continue

        fclass = _finding_class(finding)
        entry = SAFE_PATCH_TABLE.get(fclass)
        if entry is None:
            continue

        finding_id = str(finding.get("id", "unknown"))
        file_path = str(finding.get("path", ""))
        if not file_path:
            continue

        # Capture diff without applying
        diff, error = _run_ruff(str(repo_path), file_path, entry["check_cmd"])

        if error:
            # Ruff failed — record error result without writing patch/verify files
            results.append(
                {
                    "id": finding_id,
                    "class": fclass,
                    "patch_path": None,
                    "verify_path": None,
                    "diff_bytes": 0,
                    "error": error,
                }
            )
            continue

        # Write patch file
        patch_path = proposals_dir / f"{finding_id}.patch"
        patch_path.write_text(diff, encoding="utf-8")

        # Build verify commands as list of {cmd, args, expect} dicts
        verify_commands: list[dict[str, Any]] = [
            {
                "cmd": "ruff",
                "args": [str(c) for c in entry["verify_cmd"]] + [file_path],
                "expect": entry["verify_expect"],
            }
        ]

        # Write verify JSON
        verify_payload: dict[str, Any] = {
            "packet_id": finding_id,
            "class": fclass,
            "tool": entry["tool"],
            "verify_commands": verify_commands,
            "patch_path": str(patch_path),
        }
        verify_path = proposals_dir / f"{finding_id}.verify.json"
        verify_path.write_text(
            json.dumps(verify_payload, indent=2) + "\n", encoding="utf-8"
        )

        results.append(
            {
                "id": finding_id,
                "class": fclass,
                "patch_path": str(patch_path),
                "verify_path": str(verify_path),
                "diff_bytes": len(diff),
                "error": None,
            }
        )

    return results
