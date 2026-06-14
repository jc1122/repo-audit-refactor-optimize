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
