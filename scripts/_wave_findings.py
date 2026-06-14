"""Normalize leaf outputs for the diagnosis wave runner.

Each leaf writes a slightly different JSON shape:

- most leaves write a list of shared-schema finding objects;
- the code-health umbrella writes both leaf-level files and a summary file;
- tool failures can leave partial or invalid JSON behind.

The runner only needs a stable four-field identity for baseline comparison, so
this module owns the lossy conversion from leaf output to wave identities.
Keeping that logic outside the runner keeps lane execution focused on command
construction and exit-state handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _string_value(value: Any, fallback: Any = "") -> str:
    """Return a string payload, falling back only to string fallbacks."""
    if isinstance(value, str):
        return value
    return fallback if isinstance(fallback, str) else ""


def _normalize_finding(finding: dict[str, Any], lane: str) -> dict[str, str]:
    """Convert one shared-schema finding into the wave identity shape."""
    location = finding.get("location")
    if not isinstance(location, dict):
        location = {}
    metric = finding.get("metric")
    if isinstance(metric, dict):
        metric = metric.get("name")
    if metric is None:
        metric = finding.get("signal", "")
    return {
        "leaf": _string_value(finding.get("leaf"), lane),
        "path": _string_value(finding.get("path"), location.get("path", "")),
        "symbol": _string_value(finding.get("symbol"), location.get("symbol", "")),
        "metric": "" if metric is None else str(metric),
    }


def _read_findings_file(path: Path, lane: str) -> list[dict[str, str]]:
    """Read one leaf findings file, returning an empty list on bad output."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("findings", [])
    if not isinstance(payload, list):
        return []
    return [
        _normalize_finding(item, lane) for item in payload if isinstance(item, dict)
    ]


def collect_lane_findings(lane_dir: Path, lane: str) -> list[dict[str, str]]:
    """Collect all normalized findings emitted for a lane directory."""
    findings: list[dict[str, str]] = []
    for finding_path in sorted(lane_dir.glob("*_findings.json")):
        findings.extend(_read_findings_file(finding_path, lane))
    code_health_summary = lane_dir / "code_health_summary.json"
    if code_health_summary.exists():
        findings.extend(_read_findings_file(code_health_summary, lane))
    return findings


def identity(finding: dict[str, str]) -> tuple[str, str, str, str]:
    """Canonical four-field wave identity, order-insensitive on dict keys.

    Single source of truth — consumed by both the wave's --baseline suppression and
    check_wave_baseline's convergence ratchet, so the two can never disagree.
    """
    return (
        finding.get("leaf", ""),
        finding.get("path", ""),
        finding.get("symbol", ""),
        finding.get("metric", ""),
    )


def load_baseline(path: Path) -> list[dict[str, str]]:
    """Load an accepted-residuals baseline (a JSON array of identities).

    Raises on unreadable/invalid input — never silently treats a broken baseline as
    "no suppression".
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(
            f"baseline must be a JSON array of identities, got {type(payload).__name__}"
        )
    return payload


def partition(
    findings: list[dict[str, str]], baseline: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[tuple[str, str, str, str]]]:
    """Split findings against a baseline by identity → (active, suppressed, stale).

    * active     — findings whose identity is NOT in the baseline (new work)
    * suppressed — findings whose identity IS in the baseline (accepted residuals)
    * stale      — baseline identities that matched nothing (sorted)

    The wave drops ``suppressed``; the convergence ratchet fails on ``active``
    and ``stale``.
    """
    baseline_ids = {identity(entry) for entry in baseline}
    matched: set[tuple[str, str, str, str]] = set()
    active: list[dict[str, str]] = []
    suppressed: list[dict[str, str]] = []
    for finding in findings:
        fid = identity(finding)
        if fid in baseline_ids:
            matched.add(fid)
            suppressed.append({**finding, "suppressed": True})
        else:
            active.append(finding)
    stale = sorted(baseline_ids - matched)
    return active, suppressed, stale
