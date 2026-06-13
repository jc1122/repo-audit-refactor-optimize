#!/usr/bin/env python3
"""Synthesize worker packets and mechanical patches from wave findings.

Provides two public entry points:

- ``packet_for(finding, repo)`` — convert one shared-schema finding into a
  K-7 worker-packet dict.
- ``mechanical_patches(findings, repo, out_dir)`` — for findings whose
  leaf+class is in the safe table, capture a read-only unified diff and
  write ``proposals/<id>.patch`` + ``proposals/<id>.verify.json`` without
  ever applying the patch.

Behaviour is strictly advisory; no patch is ever applied to source.
"""

from __future__ import annotations

import json
import shlex
import subprocess  # nosec B404: ruff is a pinned local tool
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# K-7 packet shape
# ---------------------------------------------------------------------------

def packet_for(finding: dict[str, Any], repo: str) -> dict[str, Any]:
    """Convert one shared-schema finding into a K-7 worker packet.

    Returns a dict with keys:
        packet_id, repo, goal, files, must_run, expected, forbidden,
        token_budget
    """
    fid: str = finding.get("id", "")
    path: str = finding.get("path", "")
    location: dict[str, Any] = (finding.get("location") or {})
    symbol: str = location.get("symbol", "") if isinstance(location, dict) else ""
    metric: dict[str, Any] = finding.get("metric")
    if not isinstance(metric, dict):
        metric = {}

    metric_name: str = metric.get("name", "")
    value = metric.get("value")
    threshold = metric.get("threshold")

    # Build goal sentence
    goal_parts: list[str] = ["Reduce"]
    if metric_name:
        goal_parts.append(metric_name)
    else:
        goal_parts.append("metric")

    goal_parts.append("of")
    if symbol:
        goal_parts.append(symbol)
    else:
        goal_parts.append("<unknown>")

    goal_parts.append("in")
    goal_parts.append(path if path else "<unknown-path>")

    if value is not None:
        goal_parts.append("from")
        goal_parts.append(_metric_repr(value))
    else:
        goal_parts.append("from current level")

    if threshold is not None:
        goal_parts.append("to <=")
        goal_parts.append(_metric_repr(threshold))
    else:
        goal_parts.append("to acceptable level")

    goal = " ".join(goal_parts)

    return {
        "packet_id": fid,
        "repo": repo,
        "goal": goal,
        "files": [path] if path else [],
        "must_run": [],
        "expected": [],
        "forbidden": [],
        "token_budget": 8000,
    }


def _metric_repr(value: object) -> str:
    """Render a metric value as a compact string."""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.1f}"
    return str(value)


# ---------------------------------------------------------------------------
# Safe mechanical-patch table
# ---------------------------------------------------------------------------

# Mapping from ``leaf/classifier`` to a handler.
# Each handler is a callable(repo: Path, finding: dict) -> (diff_text | None, error_text | None)
# Only entries listed here are considered "safe" for read-only diff generation.

SAFE_PATCH_TABLE: dict[str, str] = {
    "dead-code-audit/unused_import": "ruff_unused_import",
    "quality-audit/format_drift": "ruff_format_diff",
}


def _finding_class(finding: dict[str, Any]) -> str:
    """Return the compound class key ``leaf/classifier`` for a finding."""
    leaf = finding.get("leaf", "")
    metric = finding.get("metric")
    if isinstance(metric, dict) and metric.get("name"):
        classifier = str(metric["name"]).lower().replace(" ", "_")
    else:
        # Fall back to signal or an empty string
        classifier = str(finding.get("signal", "")).lower().replace(" ", "_")
    return f"{leaf}/{classifier}"


def _ruff_unused_import(repo: Path, finding: dict[str, Any]) -> tuple[str | None, str | None]:
    """Run ``ruff check --select F401 --diff`` on the finding's path.

    Returns (diff_text, None) on success or (None, error_message).
    """
    path = finding.get("path", "")
    if not path:
        return None, "Finding has no path"
    target = repo / path
    if not target.exists():
        return None, f"Target file does not exist: {target}"

    cmd = ["ruff", "check", "--select", "F401", "--diff", str(target)]
    try:
        result = subprocess.run(  # nosec B603: ruff is trusted local tool
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"Failed to run ruff: {exc}"

    if result.returncode not in (0, 1):
        return None, f"ruff exited {result.returncode}: {result.stderr.strip()}"

    diff = result.stdout
    if not diff.strip():
        return None, "No F401 violations found (diff is empty)"

    return diff, None


def _ruff_format_diff(repo: Path, finding: dict[str, Any]) -> tuple[str | None, str | None]:
    """Run ``ruff format --diff`` on the finding's path.

    Returns (diff_text, None) on success or (None, error_message).
    """
    path = finding.get("path", "")
    if not path:
        return None, "Finding has no path"
    target = repo / path
    if not target.exists():
        return None, f"Target file does not exist: {target}"

    cmd = ["ruff", "format", "--diff", str(target)]
    try:
        result = subprocess.run(  # nosec B603: ruff is trusted local tool
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"Failed to run ruff: {exc}"

    if result.returncode not in (0, 1):
        return None, f"ruff format exited {result.returncode}: {result.stderr.strip()}"

    diff = result.stdout
    if not diff.strip():
        return None, "No format drift found (diff is empty)"

    return diff, None


# Registry of safe handlers
_SAFE_HANDLERS: dict[str, Any] = {
    "ruff_unused_import": _ruff_unused_import,
    "ruff_format_diff": _ruff_format_diff,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def mechanical_patches(
    findings: list[dict[str, Any]],
    repo: str,
    out_dir: str,
) -> list[dict[str, Any]]:
    """Generate mechanical patches for safe-class findings.

    For each finding whose compound class is in ``SAFE_PATCH_TABLE``,
    run the corresponding handler to capture a unified diff (without
    applying it) and write:

    * ``proposals/<id>.patch`` — the unified diff
    * ``proposals/<id>.verify.json`` — verify commands and expected outcome

    Unknown classes are skipped silently.

    Returns a list of result dicts, each with keys:
        id, class, patch_path, verify_path, diff_bytes, error
    """
    repo_path = Path(repo).resolve()
    proposals_dir = Path(out_dir).resolve() / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        finding_class = _finding_class(finding)
        handler_name = SAFE_PATCH_TABLE.get(finding_class)
        if handler_name is None:
            # Unknown class — skip silently
            continue

        handler = _SAFE_HANDLERS.get(handler_name)
        if handler is None:
            continue

        fid = finding.get("id", "")
        if not fid:
            continue

        diff_text, error = handler(repo_path, finding)

        result: dict[str, Any] = {
            "id": fid,
            "class": finding_class,
            "patch_path": None,
            "verify_path": None,
            "diff_bytes": 0,
            "error": error,
        }

        if diff_text is not None:
            patch_path = proposals_dir / f"{fid}.patch"
            patch_path.write_text(diff_text, encoding="utf-8")
            result["patch_path"] = str(patch_path)
            result["diff_bytes"] = len(diff_text.encode("utf-8"))

            # Write verify.json
            verify_payload = _build_verify_json(finding, finding_class, handler_name)
            verify_path = proposals_dir / f"{fid}.verify.json"
            verify_path.write_text(
                json.dumps(verify_payload, indent=2) + "\n",
                encoding="utf-8",
            )
            result["verify_path"] = str(verify_path)

        results.append(result)

    return results


def _build_verify_json(
    finding: dict[str, Any],
    finding_class: str,
    handler_name: str,
) -> dict[str, Any]:
    """Build the verify.json payload for a safe patch."""
    path = finding.get("path", "")
    fid = finding.get("id", "")

    if handler_name == "ruff_unused_import":
        return {
            "packet_id": fid,
            "class": finding_class,
            "verify_commands": [
                {
                    "cmd": f"ruff check --select F401 {shlex.quote(path)}",
                    "expect": "exit 0 (no unused imports remain)",
                },
                {
                    "cmd": f"python3 -m pytest -q --color=no",
                    "expect": "All tests pass (no regressions)",
                },
            ],
            "expected_outcome": "No F401 violations; tests pass.",
        }

    if handler_name == "ruff_format_diff":
        return {
            "packet_id": fid,
            "class": finding_class,
            "verify_commands": [
                {
                    "cmd": f"ruff format --check {shlex.quote(path)}",
                    "expect": "exit 0 (formatted correctly)",
                },
                {
                    "cmd": f"python3 -m pytest -q --color=no",
                    "expect": "All tests pass (no regressions)",
                },
            ],
            "expected_outcome": "Format check passes; tests pass.",
        }

    return {
        "packet_id": fid,
        "class": finding_class,
        "verify_commands": [],
        "expected_outcome": "Unknown handler; verify manually.",
    }


# ---------------------------------------------------------------------------
# Lightweight CLI for smoke testing
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Smoke-test entry point — not part of the public API."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Synthesize worker packets and mechanical patches."
    )
    parser.add_argument("--findings", type=Path, help="Path to findings JSON array")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--out-dir", default="out", help="Output directory")
    parser.add_argument("--packet-only", action="store_true", help="Only print packet summaries")
    args = parser.parse_args(argv)

    if not args.findings:
        print("Usage: python3 scripts/synthesize_packets.py --findings <path>", file=sys.stderr)
        return 1

    findings = json.loads(args.findings.read_text(encoding="utf-8"))
    if not isinstance(findings, list):
        findings = []

    repo = str(Path(args.repo).resolve())

    if args.packet_only:
        for finding in findings:
            packet = packet_for(finding, repo)
            print(json.dumps(packet))
        return 0

    results = mechanical_patches(findings, repo, str(args.out_dir))
    for r in results:
        status = "PATCHED" if r["patch_path"] else f"SKIPPED ({r['error']})"
        print(f"{r['id']}: {r['class']} -> {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
