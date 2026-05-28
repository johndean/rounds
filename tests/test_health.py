"""Phase 1 smoke test — /v1/health must return ok."""
import os

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    client = TestClient(app)
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    # Backend wraps every JSON response in the §9.1 envelope:
    # {success, data, error, meta}. The actual health payload is under `data`.
    assert body["data"]["status"] == "ok"
    assert "version" in body["data"]


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


def test_database_url_normalizes_to_asyncpg(monkeypatch):
    """
    Railway's ${{Postgres.DATABASE_URL}} resolves to `postgresql://` (psycopg2 scheme).
    The app uses async SQLAlchemy + asyncpg, which needs `postgresql+asyncpg://`.
    The Settings validator must rewrite the scheme transparently.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host.railway.internal:5432/railway")
    # Re-import so Settings re-reads env
    from importlib import reload

    from app import config as cfg
    reload(cfg)
    assert cfg.settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert "host.railway.internal:5432/railway" in cfg.settings.DATABASE_URL


def test_database_url_passthrough_when_already_asyncpg(monkeypatch):
    """If DATABASE_URL already carries the asyncpg scheme, it stays unchanged."""
    original = "postgresql+asyncpg://user:pw@localhost:5432/rounds"
    monkeypatch.setenv("DATABASE_URL", original)
    from importlib import reload

    from app import config as cfg
    reload(cfg)
    assert cfg.settings.DATABASE_URL == original
