import importlib
import json
import pytest

wf = importlib.import_module("scripts._wave_findings")
cwb = importlib.import_module("scripts.check_wave_baseline")

FINDINGS = [
    {"leaf": "complexity", "path": "scripts/a.py", "symbol": "<module>", "metric": "maintainability_index"},
    {"leaf": "security", "path": "scripts/b.py", "symbol": "f", "metric": "B603"},
]


def test_partition_suppresses_exact_matches():
    baseline = [{"leaf": "complexity", "path": "scripts/a.py", "symbol": "<module>", "metric": "maintainability_index"}]
    active, suppressed, stale = wf.partition(FINDINGS, baseline)
    assert [f["path"] for f in active] == ["scripts/b.py"]
    assert suppressed[0]["path"] == "scripts/a.py" and suppressed[0]["suppressed"] is True
    assert stale == []


def test_partition_reports_stale_entries():
    baseline = [{"leaf": "complexity", "path": "scripts/gone.py", "symbol": "<module>", "metric": "maintainability_index"}]
    active, suppressed, stale = wf.partition(FINDINGS, baseline)
    assert len(active) == 2 and suppressed == []
    assert stale == [("complexity", "scripts/gone.py", "<module>", "maintainability_index")]


def test_identity_is_order_insensitive():
    a = {"leaf": "x", "path": "y", "symbol": "z", "metric": "m"}
    b = {"metric": "m", "symbol": "z", "path": "y", "leaf": "x"}
    assert wf.identity(a) == wf.identity(b)


def test_check_wave_baseline_reuses_the_shared_identity():
    # the convergence ratchet and the wave's --baseline must agree on identity (single source).
    f = {"leaf": "x", "path": "y", "symbol": "z", "metric": "m"}
    assert cwb.identities([f]) == {wf.identity(f)}


def test_normalize_carries_metric_value_and_threshold():
    raw = {"leaf": "complexity", "path": "a.py",
           "location": {"symbol": "f"},
           "metric": {"name": "cyclomatic", "value": 40, "threshold": 10}}
    norm = wf._normalize_finding(raw, "code-health")
    assert norm["metric"] == "cyclomatic"
    assert norm["value"] == 40
    assert norm["threshold"] == 10
    # identity is unchanged — value rides alongside, not inside
    assert wf.identity(norm) == ("complexity", "a.py", "f", "cyclomatic")


def test_load_baseline_rejects_non_array(tmp_path):
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(ValueError):
        wf.load_baseline(bad)


def test_load_baseline_raises_on_bad_json(tmp_path):
    bad = tmp_path / "b.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        wf.load_baseline(bad)


def test_load_baseline_returns_the_array(tmp_path):
    rows = [{"leaf": "x", "path": "p", "symbol": "s", "metric": "m"}]
    good = tmp_path / "b.json"
    good.write_text(json.dumps(rows), encoding="utf-8")
    assert wf.load_baseline(good) == rows


# --- #5 mutation survivors: _string_value -------------------------------


def test_string_value_returns_string_payload_unchanged():
    assert wf._string_value("hello") == "hello"


def test_string_value_uses_string_fallback_for_non_string():
    assert wf._string_value(None, "fb") == "fb"
    assert wf._string_value(123, "fb") == "fb"


def test_string_value_default_fallback_is_empty_string():
    assert wf._string_value(None) == ""


def test_string_value_non_string_fallback_collapses_to_empty():
    # a non-string fallback must NOT leak through; collapses to "".
    assert wf._string_value(None, 42) == ""


# --- #5 mutation survivors: _normalize_finding branches ------------------


def test_normalize_falls_back_to_location_path_and_symbol():
    raw = {"leaf": "complexity",
           "location": {"path": "scripts/a.py", "symbol": "f"},
           "metric": {"name": "cyclomatic"}}
    norm = wf._normalize_finding(raw, "code-health")
    assert norm["path"] == "scripts/a.py"
    assert norm["symbol"] == "f"


def test_normalize_top_level_path_wins_over_location():
    raw = {"leaf": "complexity", "path": "top.py",
           "location": {"path": "loc.py", "symbol": "g"},
           "metric": {"name": "cyclomatic"}}
    norm = wf._normalize_finding(raw, "lane")
    assert norm["path"] == "top.py"


def test_normalize_leaf_falls_back_to_lane():
    raw = {"path": "a.py", "metric": {"name": "cyclomatic"}}
    norm = wf._normalize_finding(raw, "the-lane")
    assert norm["leaf"] == "the-lane"


def test_normalize_metric_falls_back_to_signal_when_no_metric_name():
    raw = {"leaf": "dead-code", "path": "a.py", "signal": "DELETE"}
    norm = wf._normalize_finding(raw, "lane")
    assert norm["metric"] == "DELETE"


def test_normalize_metric_empty_when_neither_metric_nor_signal():
    raw = {"leaf": "x", "path": "a.py"}
    norm = wf._normalize_finding(raw, "lane")
    assert norm["metric"] == ""


def test_normalize_non_dict_location_is_ignored():
    raw = {"leaf": "x", "path": "a.py", "location": "not-a-dict",
           "metric": {"name": "m"}}
    norm = wf._normalize_finding(raw, "lane")
    assert norm["path"] == "a.py" and norm["symbol"] == ""


def test_normalize_non_dict_metric_passes_through_as_string():
    # a scalar (non-dict) metric is kept verbatim; no value/threshold extracted.
    raw = {"leaf": "x", "path": "a.py", "metric": "scalar", "signal": "LINT"}
    norm = wf._normalize_finding(raw, "lane")
    assert norm["value"] is None and norm["threshold"] is None
    assert norm["metric"] == "scalar"


# --- #5 mutation survivors: identity default behaviour -------------------


def test_identity_defaults_missing_keys_to_empty_string():
    assert wf.identity({}) == ("", "", "", "")
    assert wf.identity({"leaf": "x"}) == ("x", "", "", "")


def test_identity_each_field_is_positionally_distinct():
    f = {"leaf": "L", "path": "P", "symbol": "S", "metric": "M"}
    assert wf.identity(f) == ("L", "P", "S", "M")


# --- #5 mutation survivors: _read_findings_file (was untested) -----------


def test_read_findings_file_normalizes_list_payload(tmp_path):
    p = tmp_path / "x_findings.json"
    p.write_text(json.dumps([
        {"leaf": "c", "path": "a.py", "location": {"symbol": "f"},
         "metric": {"name": "cyclomatic", "value": 5, "threshold": 10}},
    ]), encoding="utf-8")
    out = wf._read_findings_file(p, "lane")
    assert len(out) == 1
    assert out[0]["path"] == "a.py" and out[0]["metric"] == "cyclomatic"


def test_read_findings_file_extracts_findings_key_from_dict(tmp_path):
    p = tmp_path / "summary.json"
    p.write_text(json.dumps({"findings": [
        {"leaf": "c", "path": "a.py", "metric": {"name": "m"}},
    ]}), encoding="utf-8")
    out = wf._read_findings_file(p, "lane")
    assert [f["path"] for f in out] == ["a.py"]


def test_read_findings_file_bad_json_returns_empty(tmp_path):
    p = tmp_path / "broken_findings.json"
    p.write_text("{ not json", encoding="utf-8")
    assert wf._read_findings_file(p, "lane") == []


def test_read_findings_file_missing_file_returns_empty(tmp_path):
    assert wf._read_findings_file(tmp_path / "nope.json", "lane") == []


def test_read_findings_file_non_list_non_dict_returns_empty(tmp_path):
    p = tmp_path / "scalar_findings.json"
    p.write_text(json.dumps(42), encoding="utf-8")
    assert wf._read_findings_file(p, "lane") == []


def test_read_findings_file_skips_non_dict_items(tmp_path):
    p = tmp_path / "mixed_findings.json"
    p.write_text(json.dumps([
        "not-a-dict",
        {"leaf": "c", "path": "a.py", "metric": {"name": "m"}},
    ]), encoding="utf-8")
    out = wf._read_findings_file(p, "lane")
    assert [f["path"] for f in out] == ["a.py"]


# --- #5 mutation survivors: collect_lane_findings (was untested) ---------


def test_collect_lane_findings_reads_all_findings_globs(tmp_path):
    (tmp_path / "complexity_findings.json").write_text(
        json.dumps([{"leaf": "complexity", "path": "a.py", "metric": {"name": "ci"}}]),
        encoding="utf-8")
    (tmp_path / "security_findings.json").write_text(
        json.dumps([{"leaf": "security", "path": "b.py", "metric": {"name": "B1"}}]),
        encoding="utf-8")
    out = wf.collect_lane_findings(tmp_path, "lane")
    assert sorted(f["path"] for f in out) == ["a.py", "b.py"]


def test_collect_lane_findings_ignores_non_findings_files(tmp_path):
    (tmp_path / "report.json").write_text(
        json.dumps([{"leaf": "x", "path": "skip.py", "metric": {"name": "m"}}]),
        encoding="utf-8")
    assert wf.collect_lane_findings(tmp_path, "lane") == []


def test_collect_lane_findings_includes_code_health_summary(tmp_path):
    (tmp_path / "code_health_summary.json").write_text(
        json.dumps([{"leaf": "umbrella", "path": "c.py", "metric": {"name": "m"}}]),
        encoding="utf-8")
    out = wf.collect_lane_findings(tmp_path, "code-health")
    assert [f["path"] for f in out] == ["c.py"]


def test_collect_lane_findings_empty_dir_is_empty(tmp_path):
    assert wf.collect_lane_findings(tmp_path, "lane") == []
