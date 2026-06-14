import importlib
import json
from pathlib import Path

va = importlib.import_module("scripts.validate_accept")


def _write(tmp: Path, payload) -> Path:
    p = tmp / "accept.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_valid_file_exits_zero(tmp_path, capsys):
    f = _write(tmp_path, {"version": 1, "accept": [
        {"match": {"kind": "path", "glob": "x"}, "reason": "r"}]})
    rc = va.main(["--file", str(f)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "pass"


def test_invalid_file_exits_one_with_defect(tmp_path, capsys):
    f = _write(tmp_path, {"version": 1, "accept": [{"match": {"kind": "path"}, "reason": "r"}]})
    rc = va.main(["--file", str(f)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["status"] == "fail" and out["defects"]


def test_missing_file_exits_one(tmp_path, capsys):
    rc = va.main(["--file", str(tmp_path / "nope.json")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["status"] == "fail"
