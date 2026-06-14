"""Normalize redundancy findings + triage rows into RemediationItems.

The only module that knows the input schemas. Stdlib only, deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# leaf -> remediation class (the gate ladder key, see scripts.mprr_gate)
_CLASS_BY_LEAF: dict[str, str] = {
    "dead-code": "mechanical",
    "duplication": "refactor",
    "test-redundancy": "test_removal",
}
_REDUNDANCY_LEAVES = frozenset(_CLASS_BY_LEAF)
_PATH_RE = re.compile(r"[\w./-]+\.(?:py|js|ts|jsx|tsx)")


@dataclass(frozen=True)
class RemediationItem:
    id: str
    lane: str
    signal: str
    files: tuple[str, ...]
    remediation_class: str
    confidence: str
    finding: dict[str, Any]


def _files_for(finding: dict[str, Any]) -> tuple[str, ...]:
    paths = {str(finding.get("path", "")).strip()}
    if str(finding.get("signal", "")) in {"EXTRACT", "MERGE"}:
        raw = str((finding.get("evidence") or {}).get("raw") or "")
        paths.update(_PATH_RE.findall(raw))
    return tuple(sorted(p for p in paths if p))


def normalize(findings: list[dict[str, Any]]) -> list[RemediationItem]:
    items: list[RemediationItem] = []
    for f in findings:
        leaf = str(f.get("leaf", ""))
        if leaf not in _REDUNDANCY_LEAVES:
            continue
        items.append(
            RemediationItem(
                id=str(f.get("id", "")),
                lane=leaf,
                signal=str(f.get("signal", "")),
                files=_files_for(f),
                remediation_class=_CLASS_BY_LEAF[leaf],
                confidence=str(f.get("confidence", "low")),
                finding=f,
            )
        )
    return sorted(items, key=lambda it: it.id)


def from_triage_report(rows: list[dict[str, Any]]) -> list[RemediationItem]:
    """Adapt test-redundancy-triage rows. Only high-confidence DELETE/MERGE qualify."""
    items: list[RemediationItem] = []
    for r in rows:
        decision = str(r.get("validation_decision", ""))
        if not decision.endswith("_HIGH") or not decision.startswith(
            ("DELETE", "MERGE")
        ):
            continue
        nodeid = str(r.get("test_nodeid", ""))
        path = nodeid.split("::", 1)[0]
        if not path:
            continue
        items.append(
            RemediationItem(
                id=str(r.get("id") or nodeid),
                lane="test-redundancy",
                signal=decision.split("_", 1)[0],  # DELETE | MERGE
                files=(path,),
                remediation_class="test_removal",
                confidence="high",
                finding=dict(r),
            )
        )
    return sorted(items, key=lambda it: it.id)
