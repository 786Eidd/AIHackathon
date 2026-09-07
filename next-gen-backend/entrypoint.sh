#!/usr/bin/env bash
# entrypoint.sh

set -euo pipefail

PORT="${PORT:-8000}"

if [ "${DOWNLOAD_MODELS:-false}" = "true" ]; then
    echo "[entrypoint] Downloading models..."
    python scripts/download_models.py || \
        echo "[entrypoint] Model download failed; continuing with local models."
fi

# Camera capture and analysis threads live inside this process and share one
# copy of the models, so the server must run single-worker. Multiple uvicorn
# workers would each load the models and each start their own capture threads,
# giving duplicate events per camera.
echo "[entrypoint] Starting NexGen live surveillance API on port ${PORT}"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers 1 \
    --timeout-graceful-shutdown 30
