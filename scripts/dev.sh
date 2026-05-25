#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

echo "=> Starting backend on :8000"
cd backend
. .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$ROOT/logs/backend.log" 2>&1 &
echo $! > "$ROOT/logs/backend.pid"
cd "$ROOT"

echo "=> Starting frontend on :5173"
cd frontend
nohup npm run dev -- --host 0.0.0.0 > "$ROOT/logs/frontend.log" 2>&1 &
echo $! > "$ROOT/logs/frontend.pid"
cd "$ROOT"

sleep 3
echo
echo "=== Services started ==="
echo "Backend:  http://localhost:8000  (logs: tail -f logs/backend.log)"
echo "Frontend: http://localhost:5173  (logs: tail -f logs/frontend.log)"
echo
echo "Stop with: make stop"
