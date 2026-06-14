"""Anti-drift guard: every accepted-residual identity must be justified in the ledger.

Self-audit integrity gap (found during the v0.7.x dogfood loop): `wave_frozen.md`
documented only 7 rows while the baseline held 13 — the ledger and the baseline had
silently diverged, violating the prioritization rule that every accepted-residual row
carries a justification. Phase 2 migrated the baseline into `.repo-audit/accept.json`;
this test now reads the report-stage `finding` entries from there. It runs in the
existing CI pytest job (no external audit leaves required), so the drift cannot recur.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_accepted_finding_is_documented_in_the_frozen_ledger():
    policy = json.loads(
        (ROOT / ".repo-audit" / "accept.json").read_text(encoding="utf-8")
    )
    ledger = (ROOT / "scripts" / "wave_frozen.md").read_text(encoding="utf-8")
    findings = [
        e["match"]
        for e in policy["accept"]
        if e["match"]["kind"] == "finding" and "report" in e["applies"]
    ]
    undocumented = [
        m
        for m in findings
        if m["path"] not in ledger or m["symbol"] not in ledger
    ]
    assert not undocumented, (
        f"{len(undocumented)} accept.json finding row(s) lack a wave_frozen.md "
        f"justification (ledger/baseline drift): {undocumented}"
    )
