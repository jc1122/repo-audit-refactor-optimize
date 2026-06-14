import json
import pytest
import scripts.run_instruction_eval as ev


def test_pass_when_actual_equals_expected():
    res = ev.score_eval(skill="complexity-audit", expected_rows=3,
                        model_findings=[{"x": 1}, {"x": 2}, {"x": 3}],
                        model="claude-opus-4-8")
    assert res["expected_rows"] == 3
    assert res["actual_rows"] == 3
    assert res["pass"] is True
    assert res["skill"] == "complexity-audit"
    assert res["model"] == "claude-opus-4-8"


def test_drift_is_advisory_not_pass():
    res = ev.score_eval(skill="complexity-audit", expected_rows=3,
                        model_findings=[{"x": i} for i in range(5)],
                        model="claude-opus-4-8")
    assert res["pass"] is False
    assert res["actual_rows"] == 5
    # drift produces an advisory finding + a candidate lesson, never raises
    adv = ev.advisory_outputs(res)
    assert adv["finding"]["signal"] == "EVAL"
    assert adv["lesson"]["tier"] == "candidate"


def test_advisory_outputs_empty_on_pass():
    res = ev.score_eval(skill="complexity-audit", expected_rows=3,
                        model_findings=[1, 2, 3], model="claude-opus-4-8")
    adv = ev.advisory_outputs(res)
    assert adv["finding"] is None
    assert adv["lesson"] is None


# --- _load_expected: int literal, JSON-int, JSON-dict, and error branches ---
def test_load_expected_int_literal():
    assert ev._load_expected("3") == 3


def test_load_expected_json_bare_int(tmp_path):
    p = tmp_path / "exp.json"
    p.write_text("7", encoding="utf-8")
    assert ev._load_expected(str(p)) == 7


def test_load_expected_json_dict(tmp_path):
    p = tmp_path / "exp.json"
    p.write_text(json.dumps({"expected_rows": 5}), encoding="utf-8")
    assert ev._load_expected(str(p)) == 5


def test_load_expected_missing_file_raises():
    with pytest.raises(ValueError, match="neither an int nor an existing file"):
        ev._load_expected("/no/such/file.json")


def test_load_expected_bool_json_raises(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("true", encoding="utf-8")
    with pytest.raises(ValueError, match="not an int payload"):
        ev._load_expected(str(p))


def test_load_expected_bad_dict_raises(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"nope": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="must be an int or"):
        ev._load_expected(str(p))


# --- _load_model_findings: valid array, missing, non-array ---
def test_load_model_findings_valid(tmp_path):
    p = tmp_path / "mf.json"
    p.write_text(json.dumps([{"a": 1}, {"b": 2}]), encoding="utf-8")
    assert ev._load_model_findings(str(p)) == [{"a": 1}, {"b": 2}]


def test_load_model_findings_missing_raises():
    with pytest.raises(ValueError, match="file does not exist"):
        ev._load_model_findings("/no/such.json")


def test_load_model_findings_non_array_raises(tmp_path):
    p = tmp_path / "mf.json"
    p.write_text(json.dumps({"not": "array"}), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON array"):
        ev._load_model_findings(str(p))


# --- _build_parser ---
def test_build_parser_parses_required_args_with_default_model():
    parser = ev._build_parser()
    ns = parser.parse_args(
        ["--skill", "complexity-audit", "--expected", "3", "--model-findings", "mf.json"]
    )
    assert ns.skill == "complexity-audit"
    assert ns.expected == "3"
    assert ns.model_findings == "mf.json"
    assert ns.model == "claude-opus-4-8"


# --- main: pass, drift, two error paths, default out path ---
def test_main_pass_writes_artifact_and_returns_zero(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([{"x": 1}, {"x": 2}, {"x": 3}]), encoding="utf-8")
    out = tmp_path / "eval.json"
    rc = ev.main(
        ["--skill", "complexity-audit", "--expected", "3",
         "--model-findings", str(mf), "--out", str(out)]
    )
    assert rc == 0
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["pass"] is True
    assert artifact["advisory"]["finding"] is None


def test_main_drift_writes_advisory_finding(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([{"x": i} for i in range(5)]), encoding="utf-8")
    out = tmp_path / "eval.json"
    rc = ev.main(
        ["--skill", "complexity-audit", "--expected", "3",
         "--model-findings", str(mf), "--out", str(out)]
    )
    assert rc == 0
    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["pass"] is False
    assert artifact["advisory"]["finding"]["signal"] == "EVAL"


def test_main_malformed_model_findings_returns_two(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps({"not": "array"}), encoding="utf-8")
    rc = ev.main(
        ["--skill", "x", "--expected", "1", "--model-findings", str(mf),
         "--out", str(tmp_path / "o.json")]
    )
    assert rc == 2


def test_main_malformed_expected_returns_two(tmp_path):
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([1]), encoding="utf-8")
    rc = ev.main(
        ["--skill", "x", "--expected", "/no/such.json",
         "--model-findings", str(mf), "--out", str(tmp_path / "o.json")]
    )
    assert rc == 2


def test_main_default_out_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    rc = ev.main(["--skill", "complexity-audit", "--expected", "3", "--model-findings", str(mf)])
    assert rc == 0
    assert (tmp_path / "eval_complexity-audit.json").is_file()
