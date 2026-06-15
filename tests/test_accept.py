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


def test_parse_entry_accepts_numeric_max_value():
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "x", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "accepted at 12; tracked in CHANGELOG v0.9.0",
        "max_value": 12}]}
    policy = acc._parse_policy(raw)
    assert policy[0].max_value == 12


def test_parse_entry_rejects_non_numeric_max_value():
    raw = {"version": 1, "accept": [{
        "match": {"kind": "finding", "leaf": "x", "path": "a.py",
                  "symbol": "f", "metric": "cyclomatic"},
        "reason": "r", "max_value": "twelve"}]}
    with pytest.raises(acc.AcceptError):
        acc._parse_policy(raw)


def _policy(entries):
    return acc.AcceptPolicy([acc._parse_entry(e, i) for i, e in enumerate(entries)])


WAVE_FINDING = {"leaf": "complexity", "path": "scripts/a.py",
                "symbol": "<module>", "metric": "maintainability_index"}


def test_finding_kind_exact_match():
    p = _policy([{"match": {"kind": "finding", **WAVE_FINDING}, "reason": "r"}])
    assert p.matches(WAVE_FINDING, "report") is not None
    other = {**WAVE_FINDING, "path": "scripts/b.py"}
    assert p.matches(other, "report") is None


def test_path_kind_matches_path_attr():
    p = _policy([{"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "r"}])
    assert p.matches({"path": "skills/x/tests/fixtures/dirty.py"}, "report") is not None
    assert p.matches({"path": "scripts/a.py"}, "report") is None


def test_path_kind_matches_files_list_for_engine():
    p = _policy([{"match": {"kind": "path", "glob": "**/fixtures/**"}, "reason": "r"}])
    finding = {"files": ["src/x.py", "tests/fixtures/y.py"]}
    assert p.matches(finding, "remediation") is not None


def test_rule_kind_leaf_and_metric_subset():
    p = _policy([{"match": {"kind": "rule", "leaf": "hotspot",
                            "metric": "churn_complexity_product"}, "reason": "r"}])
    assert p.matches({"leaf": "hotspot", "path": "CHANGELOG.md", "symbol": "x",
                      "metric": "churn_complexity_product"}, "report") is not None
    assert p.matches({"leaf": "hotspot", "metric": "other"}, "report") is None


def test_applies_scopes_the_stage():
    p = _policy([{"match": {"kind": "path", "glob": "x.py"}, "reason": "r",
                  "applies": ["remediation"]}])
    assert p.matches({"path": "x.py"}, "remediation") is not None
    assert p.matches({"path": "x.py"}, "report") is None


def test_partition_splits_and_reports_stale():
    p = _policy([
        {"match": {"kind": "finding", **WAVE_FINDING}, "reason": "accepted"},
        {"match": {"kind": "path", "glob": "never/**"}, "reason": "dead"},
    ])
    other = {**WAVE_FINDING, "path": "scripts/b.py"}
    active, accepted, stale = p.partition([WAVE_FINDING, other], "report")
    assert [f["path"] for f in active] == ["scripts/b.py"]
    assert accepted[0]["accepted"] is True and accepted[0]["accept_reason"] == "accepted"
    assert any("never/**" in s for s in stale)


def test_partition_marks_expired():
    p = _policy([{"match": {"kind": "path", "glob": "x.py"}, "reason": "r",
                  "expires": "2000-01-01"}])
    active, accepted, stale = p.partition([{"path": "x.py"}], "report")
    assert active == [] and accepted[0]["expired"] is True
