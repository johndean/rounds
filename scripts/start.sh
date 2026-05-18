#!/usr/bin/env bash
# Container entrypoint. Decodes GCP_KEY_B64 (Railway) into a real file when present,
# then dispatches to api or worker role based on the first arg.
set -euo pipefail

if [[ -n "${GCP_KEY_B64:-}" ]]; then
  echo "$GCP_KEY_B64" | base64 -d > /etc/gcp/sa.json
  export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-/etc/gcp/sa.json}"
fi

# Role resolution:
#   1. RAILWAY_SERVICE_NAME matches a worker name — ALWAYS use "worker"
#      (the worker service inherits the default startCommand from
#      railway.json which is "bash scripts/start.sh api" — that "api"
#      arg would otherwise force the worker to run uvicorn and ingest
#      jobs sit in Redis forever).
#   2. Explicit $1 argument
#   3. RAILWAY_SERVICE_NAME otherwise (api / migrate)
#   4. Fallback to "api"
if [[ -n "${RAILWAY_SERVICE_NAME:-}" ]] && \
   [[ "${RAILWAY_SERVICE_NAME,,}" =~ ^(worker|celery|.*-worker)$ ]]; then
  role="worker"
elif [[ -n "${1:-}" ]]; then
  role="$1"
elif [[ -n "${RAILWAY_SERVICE_NAME:-}" ]]; then
  case "${RAILWAY_SERVICE_NAME,,}" in
    *migrate*) role="migrate" ;;
    *)         role="api" ;;
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
