"""Tests for scripts/mprr_normalize.py."""
from __future__ import annotations
import importlib, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
norm = importlib.import_module("scripts.mprr_normalize")


def _f(**kw):
    base = {"id": "a", "leaf": "dead-code", "signal": "DELETE",
            "path": "pkg/m.py", "evidence": {"raw": ""}, "confidence": "high"}
    base.update(kw); return base


def test_dead_code_is_mechanical_single_file():
    [it] = norm.normalize([_f()])
    assert it.remediation_class == "mechanical"
    assert it.files == ("pkg/m.py",)
    assert it.lane == "dead-code"


def test_duplication_extract_is_refactor_and_pulls_partner_file():
    raw = "Clone of pkg/a.py:10-20 and pkg/b.py:30-40"
    [it] = norm.normalize([_f(leaf="duplication", signal="EXTRACT",
                              path="pkg/a.py", evidence={"raw": raw})])
    assert it.remediation_class == "refactor"
    assert it.files == ("pkg/a.py", "pkg/b.py")


def test_non_redundancy_leaf_is_dropped():
    assert norm.normalize([_f(leaf="complexity", signal="SIMPLIFY")]) == []


def test_triage_high_delete_becomes_test_removal_item():
    rows = [{"test_nodeid": "tests/test_x.py::test_a", "validation_decision": "DELETE_SAFE_HIGH"}]
    [it] = norm.from_triage_report(rows)
    assert it.remediation_class == "test_removal"
    assert it.confidence == "high"
    assert it.files == ("tests/test_x.py",)


def test_triage_non_high_is_dropped():
    rows = [{"test_nodeid": "tests/test_x.py::t", "validation_decision": "DELETE_SAFE_LOW"}]
    assert norm.from_triage_report(rows) == []


def test_items_are_sorted_by_id_deterministically():
    out = norm.normalize([_f(id="b"), _f(id="a")])
    assert [it.id for it in out] == ["a", "b"]
