"""Anti-drift guard: every wave-baseline identity must be justified in the ledger.

Self-audit integrity gap (found during the v0.7.x dogfood loop): `wave_frozen.md`
documented only 7 rows while `scripts/wave_baseline.json` held 13 — the ledger and
the baseline had silently diverged, violating the prioritization rule that every
accepted-residual row carries a justification. This test runs in the existing CI
pytest job (no external audit leaves required), so the drift cannot recur unnoticed.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_baseline_identity_is_documented_in_the_frozen_ledger():
    baseline = json.loads(
        (ROOT / "scripts" / "wave_baseline.json").read_text(encoding="utf-8")
    )
    ledger = (ROOT / "scripts" / "wave_frozen.md").read_text(encoding="utf-8")
    undocumented = [
        row
        for row in baseline
        if row["path"] not in ledger or row["symbol"] not in ledger
    ]
    assert not undocumented, (
        f"{len(undocumented)} wave_baseline.json row(s) lack a wave_frozen.md "
        f"justification (ledger/baseline drift): {undocumented}"
    )
