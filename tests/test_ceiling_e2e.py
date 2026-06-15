import importlib
import json

rdw = importlib.import_module("scripts.run_diagnosis_wave")
acc = importlib.import_module("scripts._accept")


def test_ceiling_breach_lands_in_active_and_fails_gate(tmp_path):
    findings = [{"leaf": "complexity", "path": "a.py", "symbol": "f",
                 "metric": "cyclomatic", "value": 40, "threshold": 10}]
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "complexity", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "accepted at 12; CHANGELOG v0.9.0", "max_value": 12}]}
    policy = acc.AcceptPolicy(acc._parse_policy(raw))
    active = rdw._apply_accept(policy, findings, tmp_path)
    assert len(active) == 1  # breach is active, not suppressed
    sidecar = json.loads((tmp_path / "wave_findings.accepted.json").read_text())
    assert sidecar["accepted"] == [] and sidecar["stale"] == []
