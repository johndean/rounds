#!/usr/bin/env bash
# Container entrypoint. Decodes GCP_KEY_B64 (Railway) into a real file when present,
# then dispatches to api or worker role based on the first arg.
set -euo pipefail

if [[ -n "${GCP_KEY_B64:-}" ]]; then
  echo "$GCP_KEY_B64" | base64 -d > /etc/gcp/sa.json
  export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-/etc/gcp/sa.json}"
fi

role="${1:-api}"

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
