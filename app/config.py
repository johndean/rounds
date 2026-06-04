"""
Rounds settings — ports MIC audit §6 environment contract.

The 47-var table from the audit is materialized here as a single Pydantic
Settings class. Defaults match the audit table verbatim, with two exceptions:
  • Vault fields are removed (audit §5: scaffold-only; never wired).
  • VERTEX_AI_GEMINI_API_KEY removed (audit §3.3: vestigial — never read).
"""
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Required ──────────────────────────────────────────────────────
    DATABASE_URL: str
    REDIS_URL: str
    GCP_PROJECT_ID: str = "rounds-dev-local"
    GCS_BUCKET: str = "rounds-dev-local-sessions"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    API_SECRET_KEY: str
    AUTH_USERS: str  # fails fast if unset (audit §10 finding #7)

    # ── Auth ──────────────────────────────────────────────────────────
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ── Rate limiting ─────────────────────────────────────────────────
    MAX_CONCURRENT_SESSIONS: int = 3
    MAX_QUEUE_LENGTH: int = 10
    MAX_UPLOAD_SIZE_MB: int = 2048
    MAX_VIDEO_DURATION_MINUTES: int = 180

    # ── Processing — LOCKED weights (audit §6) ────────────────────────
    FRAME_SAMPLE_FPS: int = 2
    VISUAL_CHANGE_THRESHOLD: float = 8.0
    ANCHOR_CROSS_VALIDATE_WINDOW: float = 5.0
    SOFT_WINDOW_EXPANSION: float = 5.0
    BOUNDARY_MERGE_WINDOW: float = 3.0

    FUSION_WEIGHT_VISUAL: float = 0.5
    FUSION_WEIGHT_ANCHOR: float = 0.3
    FUSION_WEIGHT_SEMANTIC: float = 0.2
    FUSION_BOUNDARY_THRESHOLD: float = 0.35

    ALIGN_WEIGHT_SEMANTIC: float = 0.35
    ALIGN_WEIGHT_COVERAGE: float = 0.25
    ALIGN_WEIGHT_TEMPORAL: float = 0.25
    ALIGN_WEIGHT_SEQUENTIAL: float = 0.15
    ALIGN_SEQUENTIAL_PENALTY: float = 0.8

    IIL_DRIFT_CONFIDENCE_PENALTY: float = 0.3
    IIL_DRIFT_REALIGN_WINDOW: float = 20.0
    IIL_TIER2_DEFAULT_THRESHOLD: float = 0.7
    IIL_TIER2_MODERATE_THRESHOLD: float = 0.85

    CELERY_MAX_RETRIES: int = 3
    CELERY_RETRY_BACKOFF_BASE: int = 60
    CELERY_RETRY_JITTER: bool = True
    IDEMPOTENCY_KEY_TTL_SECONDS: int = 86400

    # ── Transcription ─────────────────────────────────────────────────
    TRANSCRIPTION_BACKEND: str = "google_stt_chunked"
    TRANSCRIPTION_CHUNK_MINUTES: int = 5

    # ── AI ────────────────────────────────────────────────────────────
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_CLASSIFY_MODEL: str = "gemini-2.5-flash-lite"
    VERTEX_AI_CLASSIFY_ENABLED: bool = False
    VERTEX_AI_LOCATION: str = "us-central1"

    # ── Misc ──────────────────────────────────────────────────────────
    ENVIRONMENT: str = "production"

    # ── Upload watchdog (Phase H' 2026-05-25) ─────────────────────────
    # Background Celery Beat task that recovers sessions stuck on
    # status='uploading' when the silent enqueue_ingest failure path in
    # /v1/gcs/upload-complete fires. Default-OFF so the deploy itself is
    # zero behavioural change; flip UPLOAD_WATCHDOG_ENABLED=true in
    # Railway worker env vars to activate. Disable instantly by setting
    # it back to false + worker restart (no code revert needed). See the
    # plan in C:\Users\JohnDean\.claude\plans\lets-start-a-new-streamed-creek.md.
    UPLOAD_WATCHDOG_ENABLED: bool = False
    UPLOAD_STUCK_THRESHOLD_SEC: int = 300       # 5min — minimum age before considering 'stuck'
    UPLOAD_WATCHDOG_INTERVAL_SEC: int = 60      # beat tick cadence
    UPLOAD_WATCHDOG_COOLDOWN_SEC: int = 600     # 10min — minimum gap between watchdog retries on same session

    # ── Validators ─────────────────────────────────────────────────────
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _coerce_asyncpg_scheme(cls, v: object) -> object:
        """
        Railway's ${{Postgres.DATABASE_URL}} expands to `postgresql://...`
        (psycopg2-style). The async SQLAlchemy engine + asyncpg driver
        used by the app requires the `postgresql+asyncpg://` scheme.
        Normalize here so the env-var value can come from any source.
        scripts/migrate.py does the reverse conversion for psycopg2.
        """
        if isinstance(v, str) and v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v


settings = Settings()  # type: ignore[call-arg]
