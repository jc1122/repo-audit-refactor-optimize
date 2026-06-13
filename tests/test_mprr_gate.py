"""Tests for scripts/mprr_gate.py — gate ladder verification."""
from __future__ import annotations
import importlib, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
gate = importlib.import_module("scripts.mprr_gate")


def test_mechanical_needs_tests_and_reaudit():
    ok, reasons = gate.verify("mechanical", {"tests_passed": True, "finding_resolved": True})
    assert ok and reasons == []
    ok, reasons = gate.verify("mechanical", {"tests_passed": False, "finding_resolved": True})
    assert not ok and any("tests" in r for r in reasons)


def test_refactor_requires_mutation_80():
    base = {"tests_passed": True, "finding_resolved": True}
    assert gate.verify("refactor", {**base, "mutation_score": 0.80})[0]
    ok, reasons = gate.verify("refactor", {**base, "mutation_score": 0.79})
    assert not ok and any("mutation" in r for r in reasons)


def test_test_removal_requires_parity_and_high_confidence():
    good = {"coverage_parity": True, "mutation_parity": True, "confidence": "high"}
    assert gate.verify("test_removal", good)[0]
    ok, reasons = gate.verify("test_removal", {**good, "confidence": "medium"})
    assert not ok and any("confidence" in r for r in reasons)


def test_unknown_class_fails_closed():
    ok, reasons = gate.verify("bogus", {})
    assert not ok and reasons
