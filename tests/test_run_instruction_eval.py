import json
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
