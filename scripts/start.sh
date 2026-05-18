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
    # Celery doesn't serve HTTP. Railway's healthcheck path /v1/health
    # would mark the worker UNHEALTHY → endless restart loop. We run
    # Celery as a background process and a tiny stdlib HTTP server in
    # the foreground to satisfy the healthcheck.
    celery -A app.tasks.celery_app.celery_app worker \
      --loglevel=info \
      --concurrency="${CELERY_CONCURRENCY:-2}" \
      --queues=celery &
    CELERY_PID=$!
    echo "[start.sh] celery pid=$CELERY_PID" >&2
    # Background watchdog — if Celery dies, kill the container so Railway
    # restarts cleanly (instead of healthcheck staying green on a zombie).
    (
      wait $CELERY_PID
      echo "[start.sh] celery exited — terminating healthcheck server" >&2
      kill -TERM 1 2>/dev/null || true
    ) &
    exec python -c "
import os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{\"status\":\"ok\",\"role\":\"worker\"}')
    def do_HEAD(self):
        self.send_response(200); self.end_headers()
    def log_message(self, *a, **kw): pass
port = int(os.environ.get('PORT', '8000'))
print(f'[worker-health] listening on :{port}', flush=True)
HTTPServer(('0.0.0.0', port), H).serve_forever()
"
    ;;
  migrate)
    exec python scripts/migrate.py
    ;;
  *)
    echo "unknown role: $role (expected: api | worker | migrate)" >&2
    exit 2
    ;;
esac
