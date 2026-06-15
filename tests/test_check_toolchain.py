import importlib

mod = importlib.import_module("scripts.check_toolchain")


def test_match_when_versions_equal():
    drift = mod.diff_versions({"pytest": "9.0.3"}, {"pytest": "9.0.3"})
    assert drift == []


def test_drift_when_version_differs():
    drift = mod.diff_versions({"pytest": "9.0.3"}, {"pytest": "8.0.0"})
    assert drift == ["pytest: pinned 9.0.3, installed 8.0.0"]


def test_drift_when_missing():
    drift = mod.diff_versions({"pytest": "9.0.3"}, {"pytest": None})
    assert drift == ["pytest: pinned 9.0.3, installed MISSING"]
