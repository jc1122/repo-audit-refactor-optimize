"""Build file-backed remediation worker packets (one finding -> one packet).

Mirrors the existing K-7 packet shape in scripts.synthesize_packets; the
must_run set is derived from the gate ladder class so a worker proves exactly
what mprr_gate.verify will check.
"""

from __future__ import annotations

from typing import Any

_TOKEN_BUDGET = 8000
_LESSON_CAP = 5

# gate-class -> verification commands the worker must run and pass
_MUST_RUN: dict[str, list[str]] = {
    "mechanical": [
        "pytest -q",
        "<re-run the finding's lane; assert the finding is gone>",
    ],
    "refactor": [
        "pytest -q",
        "mutmut run --paths-to-mutate <changed modules> (>=80% killed)",
        "<re-run duplication-audit; assert the clone is gone>",
    ],
    "test_removal": [
        "pytest -q (suite still green after removal)",
        "<coverage parity: line+branch unchanged>",
        "<mutation parity: kill-set not weakened>",
    ],
}
_EXPECTED: dict[str, list[str]] = {
    "mechanical": ["tests_passed=true", "finding_resolved=true"],
    "refactor": ["tests_passed=true", "mutation_score>=0.80", "finding_resolved=true"],
    "test_removal": ["coverage_parity=true", "mutation_parity=true", "confidence=high"],
}


def remediation_packet(item: Any, repo: str, lessons: list[str]) -> dict[str, Any]:
    cls = item.remediation_class
    action = (
        str((item.finding or {}).get("suggested_action", ""))
        or f"remediate {item.signal} finding"
    )
    return {
        "packet_id": item.id,
        "repo": repo,
        "goal": f"{action} (lane={item.lane}, signal={item.signal})",
        "files": list(item.files),  # the DECLARED allowed files (scope lock)
        "remediation_class": cls,
        "must_run": list(_MUST_RUN.get(cls, [])),
        "expected": list(_EXPECTED.get(cls, [])),
        "forbidden": [
            "edits to any file outside `files`",
            "new public API",
            "test weakening",
        ],
        "lessons": list(lessons)[:_LESSON_CAP],
        "token_budget": _TOKEN_BUDGET,
    }
