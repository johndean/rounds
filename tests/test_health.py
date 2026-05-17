"""Phase 1 smoke test — /v1/health must return ok."""
from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    client = TestClient(app)
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_locked_weights_match_audit():
    """
    Audit §6 marks fusion / alignment / IIL / celery weights as LOCKED.
    This test pins them so future changes require deliberate intent.
    """
    from app.config import settings

    assert settings.FUSION_WEIGHT_VISUAL == 0.5
    assert settings.FUSION_WEIGHT_ANCHOR == 0.3
    assert settings.FUSION_WEIGHT_SEMANTIC == 0.2
    assert settings.FUSION_BOUNDARY_THRESHOLD == 0.35

    assert settings.ALIGN_WEIGHT_SEMANTIC == 0.35
    assert settings.ALIGN_WEIGHT_COVERAGE == 0.25
    assert settings.ALIGN_WEIGHT_TEMPORAL == 0.25
    assert settings.ALIGN_WEIGHT_SEQUENTIAL == 0.15
    assert settings.ALIGN_SEQUENTIAL_PENALTY == 0.8

    assert settings.CELERY_MAX_RETRIES == 3
    assert settings.CELERY_RETRY_BACKOFF_BASE == 60
    assert settings.CELERY_RETRY_JITTER is True
