#!/usr/bin/env bash
# start_backend.sh — Start the Kora agent backend in a detached screen session.
# Usage:
#   ./scripts/start_backend.sh          # start
#   ./scripts/start_backend.sh stop     # stop
#   ./scripts/start_backend.sh status   # check
#   ./scripts/start_backend.sh logs     # tail logs

set -euo pipefail

SESSION="kora_backend"
AGENT_DIR="$(cd "$(dirname "$0")/../apps/agent" && pwd)"
LOG_FILE="/tmp/kora_backend.log"

case "${1:-start}" in
  start)
    if screen -list | grep -q "$SESSION"; then
      echo "Backend is already running (screen session: $SESSION)"
      exit 0
    fi
    echo "Starting Kora backend on http://127.0.0.1:8765 ..."
    screen -dmS "$SESSION" bash -c "
      cd '$AGENT_DIR'
      exec python3 -m uvicorn main:app \
        --host 127.0.0.1 \
        --port 8765 \
        --reload \
        2>&1 | tee '$LOG_FILE'
    "
    sleep 3
    if screen -list | grep -q "$SESSION"; then
      echo "✓ Backend running in screen session '$SESSION'"
      echo "  Logs: $LOG_FILE"
      echo "  Stop: ./scripts/start_backend.sh stop"
    else
      echo "✗ Backend failed to start. Check: $LOG_FILE"
      exit 1
    fi
    ;;
  stop)
    screen -S "$SESSION" -X quit 2>/dev/null && echo "Stopped." || echo "Not running."
    ;;
  status)
    if screen -list | grep -q "$SESSION"; then
      echo "✓ Backend is running (screen: $SESSION)"
    else
      echo "✗ Backend is not running"
    fi
    ;;
  logs)
    tail -f "$LOG_FILE"
    ;;
  *)
    echo "Usage: $0 {start|stop|status|logs}"
    exit 1
    ;;
esac
