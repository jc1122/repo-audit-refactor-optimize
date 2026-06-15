import importlib

mod = importlib.import_module("scripts.check_accept_reasons")


def test_specific_reason_passes():
    ok, defect = mod.audit_reason(
        "perflint C0206 in scripts/foo.py: dict-iter residual, CHANGELOG v0.9.0")
    assert ok and defect is None


def test_boilerplate_reason_fails():
    ok, defect = mod.audit_reason("migrated accepted residual — see the repo's frozen ledger")
    assert not ok and "boilerplate" in defect.lower()


def test_too_short_reason_fails():
    ok, defect = mod.audit_reason("accepted")
    assert not ok


def test_reason_without_concrete_token_fails():
    ok, defect = mod.audit_reason("this is a perfectly long sentence with no specifics here")
    assert not ok and "concrete" in defect.lower()
