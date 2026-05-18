#!/usr/bin/env bash
# Container entrypoint. Decodes GCP_KEY_B64 (Railway) into a real file when present,
# then dispatches to api or worker role based on the first arg.
set -euo pipefail

if [[ -n "${GCP_KEY_B64:-}" ]]; then
  echo "$GCP_KEY_B64" | base64 -d > /etc/gcp/sa.json
  export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-/etc/gcp/sa.json}"
fi

# Role resolution:
#   1. Explicit first argument wins ($1)
#   2. Railway sets RAILWAY_SERVICE_NAME — match common names
#   3. Fallback to "api"
# This means the worker service runs Celery without needing a startCommand
# override in railway.json (the default in railway.json is "bash scripts/start.sh api"
# and we don't want to fork that file per service).
if [[ -n "${1:-}" ]]; then
  role="$1"
elif [[ -n "${RAILWAY_SERVICE_NAME:-}" ]]; then
  case "${RAILWAY_SERVICE_NAME,,}" in
    worker|celery|*-worker) role="worker" ;;
    *)                       role="api" ;;
  esac
else
  role="api"
fi
echo "[start.sh] role=$role (RAILWAY_SERVICE_NAME=${RAILWAY_SERVICE_NAME:-unset}, \$1=${1:-})" >&2

case "$role" in
  api)
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips='*'
    ;;
  worker)
    exec celery -A app.tasks.celery_app.celery_app worker \
      --loglevel=info \
      --concurrency="${CELERY_CONCURRENCY:-2}" \
      --queues=celery
    ;;
  migrate)
    exec python scripts/migrate.py
    ;;
  *)
    echo "unknown role: $role (expected: api | worker | migrate)" >&2
    exit 2
    ;;
esac
