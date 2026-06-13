"""The gate ladder: what proof authorizes an unattended auto-merge, per class.

Pure: `verify` inspects a worker's reported evidence dict. The orchestrator
re-derives this evidence itself from gate artifacts — it never trusts a
worker's self-reported 'green' (L-3).
"""
from __future__ import annotations

from typing import Any

MUTATION_FLOOR = 0.80


def verify(remediation_class: str, evidence: dict[str, Any] | None) -> tuple[bool, list[str]]:
    ev = evidence or {}
    reasons: list[str] = []

    def need(ok: bool, msg: str) -> None:
        if not ok:
            reasons.append(msg)

    if remediation_class == "mechanical":
        need(ev.get("tests_passed") is True, "tests not green")
        need(ev.get("finding_resolved") is True, "lane re-audit still reports the finding")
    elif remediation_class == "refactor":
        need(ev.get("tests_passed") is True, "tests not green")
        ms = ev.get("mutation_score")
        need(isinstance(ms, (int, float)) and ms >= MUTATION_FLOOR,
             f"mutation score below {MUTATION_FLOOR}")
        need(ev.get("finding_resolved") is True, "duplication re-audit still reports the clone")
    elif remediation_class == "test_removal":
        need(ev.get("coverage_parity") is True, "coverage parity not proven")
        need(ev.get("mutation_parity") is True, "mutation parity not proven")
        need(ev.get("confidence") == "high", "triage confidence below high")
    else:
        reasons.append(f"unknown remediation_class {remediation_class!r}")

    return (not reasons, reasons)
