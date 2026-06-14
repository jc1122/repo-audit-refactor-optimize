import importlib
import json
from pathlib import Path

import pytest

acc = importlib.import_module("scripts._accept")


def _write(repo: Path, payload: object) -> Path:
    d = repo / ".repo-audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "accept.json").write_text(json.dumps(payload), encoding="utf-8")
    return repo


def test_missing_file_is_empty_policy(tmp_path: Path):
    policy = acc.load_accept(tmp_path)
    assert policy.entries == []


def test_loads_valid_policy(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "intentional"},
    ]})
    policy = acc.load_accept(tmp_path)
    assert len(policy.entries) == 1
    e = policy.entries[0]
    assert e.kind == "path" and e.reason == "intentional"
    assert e.applies == frozenset({"report", "remediation"})  # default both


def test_malformed_json_raises(tmp_path: Path):
    d = tmp_path / ".repo-audit"; d.mkdir()
    (d / "accept.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_missing_reason_raises(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [{"match": {"kind": "path", "glob": "x"}}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_unknown_kind_raises(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "nope"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_bad_applies_value_raises(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "x"}, "reason": "r", "applies": ["typo"]}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_path_traversal_glob_rejected(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "../escape/**"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_finding_kind_requires_four_fields(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "finding", "leaf": "c", "path": "p"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)


def test_rule_kind_requires_leaf_or_metric(tmp_path: Path):
    _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "rule"}, "reason": "r"}]})
    with pytest.raises(acc.AcceptError):
        acc.load_accept(tmp_path)
