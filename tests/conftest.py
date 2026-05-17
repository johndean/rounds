"""Shared pytest fixtures. Phase 5+ adds real ones; Phase 1 only needs the package marker."""
import os

# Ensure required settings vars are present when tests import app.config.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://rounds:rounds_dev_pw@localhost:5432/rounds")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_SECRET_KEY", "test_only_secret_change_in_prod_00000000000000000000000000")
os.environ.setdefault("AUTH_USERS", "test@vin.com:test_only_password")
os.environ.setdefault("ENVIRONMENT", "test")
