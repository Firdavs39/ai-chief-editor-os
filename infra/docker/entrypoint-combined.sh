#!/usr/bin/env bash
# Single-machine runtime: SQLite-backed alpha deploy on Fly.io.
# Boots the async worker in the background and uvicorn in the foreground.
# Both processes share the same filesystem (and therefore the same SQLite
# DB on the mounted Fly volume).
#
# Signal handling: when Fly sends SIGTERM, we forward it to the worker
# child, then let uvicorn shut down cleanly.

set -euo pipefail

# Ensure the volume mount directory exists for SQLite.
mkdir -p /data || true

# Start the worker as a background child.
echo "[entrypoint] starting worker"
python -m worker.main &
WORKER_PID=$!

shutdown() {
  echo "[entrypoint] received signal, stopping worker pid=$WORKER_PID"
  if kill -0 "$WORKER_PID" 2>/dev/null; then
    kill -TERM "$WORKER_PID" || true
    wait "$WORKER_PID" 2>/dev/null || true
  fi
  echo "[entrypoint] worker stopped"
}
trap shutdown TERM INT EXIT

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
