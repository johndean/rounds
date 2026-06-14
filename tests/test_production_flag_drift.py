"""Pins the production feature-flag contract + the drift detector.

The live features (split/merge, reorder, bulk, CMS-polls, Vertex, Help-AI) are
ON only because the Railway env sets them — their code default is False
(dark-ship). Unlike the LOCKED processing weights, nothing in code asserted
"these are live in prod," so a lost/reset env var would silently 503 with no
signal. config.EXPECTED_PRODUCTION_FLAGS is that SSOT contract;
Settings.production_flag_drift() reports any expected-on flag that's OFF, which
the startup hook logs CRITICAL and /v1/version surfaces.

Mirrors tests/test_health.py::test_locked_weights_match_audit — pinning so a
change to what's guarded requires deliberate intent.
"""
from app.config import EXPECTED_PRODUCTION_FLAGS, settings


def test_expected_production_flags_pinned():
    """Changing which features are guarded as must-be-on-in-prod requires
    deliberately editing this set (deliberate-intent posture)."""
    assert set(EXPECTED_PRODUCTION_FLAGS) == {
        "SPLIT_MERGE_ENABLED",
        "BULK_REASSIGN_ENABLED",
        "SEGMENT_REORDER_ENABLED",
        "CMS_POLLS_FROM_TABLE",
        "VERTEX_AI_CLASSIFY_ENABLED",
        "HELP_ASK_AI_ENABLED",
    }


def test_guarded_flags_are_real_bool_fields():
    """Each guarded name must be a real bool field on Settings — catches a
    renamed/removed flag silently dropping out of the guard."""
    for name in EXPECTED_PRODUCTION_FLAGS:
        assert hasattr(settings, name), f"{name} is not a Settings field"
        assert isinstance(getattr(settings, name), bool), f"{name} is not bool"


def test_dark_flags_are_not_guarded():
    """UPLOAD_WATCHDOG + SOP_DEADLINE_EMAIL are intentionally dark today. If
    they were in the expected-on set, a healthy prod would false-alarm."""
    assert "UPLOAD_WATCHDOG_ENABLED" not in EXPECTED_PRODUCTION_FLAGS
    assert "SOP_DEADLINE_EMAIL_ENABLED" not in EXPECTED_PRODUCTION_FLAGS


def test_no_drift_when_all_expected_flags_on():
    all_on = settings.model_copy(update={n: True for n in EXPECTED_PRODUCTION_FLAGS})
    assert all_on.production_flag_drift() == []


def test_drift_reports_each_off_flag():
    # Toggle each expected flag off in isolation; it must be the sole report.
    for off in EXPECTED_PRODUCTION_FLAGS:
        upd = {n: True for n in EXPECTED_PRODUCTION_FLAGS}
        upd[off] = False
        drifted = settings.model_copy(update=upd)
        assert drifted.production_flag_drift() == [off]


def test_drift_preserves_ssot_order_for_multiple_off():
    all_off = settings.model_copy(update={n: False for n in EXPECTED_PRODUCTION_FLAGS})
    # Reported in EXPECTED_PRODUCTION_FLAGS order, all of them.
    assert all_off.production_flag_drift() == list(EXPECTED_PRODUCTION_FLAGS)
