#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"
PID_FILE="$RUN_DIR/ai-novelist-web.pid"
LOG_FILE="$RUN_DIR/ai-novelist-web.log"
HOST="${AI_NOVELIST_WEB_HOST:-127.0.0.1}"
PORT="${AI_NOVELIST_WEB_PORT:-8000}"
PROVIDER="${AI_NOVELIST_MODEL_PROVIDER:-deepseek}"
MODEL="${AI_NOVELIST_DEEPSEEK_MODEL:-deepseek-chat}"
TIMEOUT="${AI_NOVELIST_WEB_TIMEOUT:-180}"

load_env() {
  # The user's shell config already contains the DeepSeek key. Source it here
  # so the web process gets the same runtime credentials as an interactive CLI.
  if [[ -f "$HOME/.bashrc" ]]; then
    # shellcheck source=/dev/null
    set +u
    source "$HOME/.bashrc"
    set -u
  fi
}

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

start() {
  mkdir -p "$RUN_DIR"
  if is_running; then
    echo "ai-novelist web is already running: pid $(cat "$PID_FILE")"
    return 0
  fi
  load_env
  if [[ "$PROVIDER" == "deepseek" && -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "DEEPSEEK_API_KEY is not set. Add it to ~/.bashrc or export it before running this script." >&2
    return 1
  fi
  cd "$ROOT_DIR"
  setsid "$ROOT_DIR/.venv/bin/ai-novelist" web \
    --host "$HOST" \
    --port "$PORT" \
    --provider "$PROVIDER" \
    --model "$MODEL" \
    --timeout "$TIMEOUT" \
    >>"$LOG_FILE" 2>&1 </dev/null &
  echo "$!" >"$PID_FILE"
  sleep 1
  if ! is_running; then
    echo "ai-novelist web failed to start. See $LOG_FILE" >&2
    return 1
  fi
  if ! curl -fsS "http://$HOST:$PORT/" >/dev/null 2>&1; then
    echo "ai-novelist web process started but HTTP check failed. See $LOG_FILE" >&2
    return 1
  fi
  echo "ai-novelist web started: http://$HOST:$PORT"
  echo "pid: $(cat "$PID_FILE")"
  echo "log: $LOG_FILE"
}

stop() {
  if ! is_running; then
    rm -f "$PID_FILE"
    echo "ai-novelist web is not running"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid"
  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "ai-novelist web stopped"
      return 0
    fi
    sleep 0.2
  done
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "ai-novelist web stopped"
}

status() {
  if is_running; then
    echo "running: pid $(cat "$PID_FILE")"
    echo "url: http://$HOST:$PORT"
    echo "log: $LOG_FILE"
  else
    echo "stopped"
    return 1
  fi
}

case "${1:-start}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
    stop
    start
    ;;
  status)
    status
    ;;
  logs)
    mkdir -p "$RUN_DIR"
    touch "$LOG_FILE"
    tail -f "$LOG_FILE"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}" >&2
    exit 2
    ;;
esac
