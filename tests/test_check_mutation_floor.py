"""Tests for the mutation-kill floor gate (#5).

The pure ``floor_violations`` logic is unit-tested against an in-line
fixture report; mutmut itself is never invoked here (that is the CI/local
smoke step, not a unit test).
"""

from __future__ import annotations

import json

import scripts.check_mutation_floor as g


# --- pure floor logic ------------------------------------------------------


def test_floor_violations_empty_when_all_meet_floor():
    report = {
        "scripts/_accept.py": 0.95,
        "scripts/_wave_findings.py": 0.80,
        "scripts/check_wave_baseline.py": 1.0,
    }
    assert g.floor_violations(report, 0.80) == []


def test_floor_violations_lists_under_floor_modules_sorted():
    report = {
        "scripts/_wave_findings.py": 0.70,
        "scripts/_accept.py": 0.55,
        "scripts/check_wave_baseline.py": 0.90,
    }
    assert g.floor_violations(report, 0.80) == [
        "scripts/_accept.py",
        "scripts/_wave_findings.py",
    ]


def test_floor_violations_boundary_is_inclusive():
    """A module exactly at the floor passes (>= floor, not > floor)."""
    report = {"scripts/_accept.py": 0.80}
    assert g.floor_violations(report, 0.80) == []


def test_floor_violations_handles_missing_kill_rate_as_violation():
    """A module the leaf could not measure (None) is a violation, not a pass."""
    report = {"scripts/_accept.py": None, "scripts/_wave_findings.py": 0.99}
    assert g.floor_violations(report, 0.80) == ["scripts/_accept.py"]


# --- argument / config parsing --------------------------------------------


def test_leaf_env_override(monkeypatch):
    monkeypatch.setenv("LEAF", "/custom/leaf.py")
    assert g._leaf() == "/custom/leaf.py"


def test_leaf_default(monkeypatch):
    monkeypatch.delenv("LEAF", raising=False)
    assert g._leaf().endswith(
        "test-effectiveness-audit/scripts/test_effectiveness_audit.py"
    )


def test_load_targets_reads_modules_and_floor(tmp_path):
    targets = tmp_path / "targets.json"
    targets.write_text(
        json.dumps({"modules": ["scripts/a.py"], "min_kill_rate": 0.7}),
        encoding="utf-8",
    )
    modules, floor = g.load_targets(targets)
    assert modules == ["scripts/a.py"]
    assert floor == 0.7


# --- main() verdict --------------------------------------------------------


def test_main_passes_when_no_violations(monkeypatch):
    monkeypatch.setattr(g, "measure_kill_rates", lambda modules: {m: 0.99 for m in modules})
    assert g.main([]) == 0


def test_main_fails_when_a_module_is_below_floor(monkeypatch, capsys):
    def _fake(modules):
        rates = {m: 0.99 for m in modules}
        rates[modules[0]] = 0.40
        return rates

    monkeypatch.setattr(g, "measure_kill_rates", _fake)
    rc = g.main([])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["status"] == "fail"
    assert out["violations"][0]["module"] == "scripts/_accept.py"
