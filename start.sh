#!/usr/bin/env bash
# 墨记 Blog 启动脚本
# 用法: ./start.sh [start|stop|restart|status]
# 环境变量: MOJI_HOST (默认 0.0.0.0)  MOJI_PORT (默认 8000)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RUN_DIR="${MOJI_RUN_DIR:-$ROOT/.run}"
PID_FILE="$RUN_DIR/moji-blog.pid"
LOG_FILE="$RUN_DIR/moji-blog.log"
HOST="${MOJI_HOST:-0.0.0.0}"
PORT="${MOJI_PORT:-8000}"
VENV_UVICORN="$ROOT/.venv/bin/uvicorn"

ensure_run_dir() {
  mkdir -p "$RUN_DIR"
}

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

resolve_uvicorn() {
  if [[ -x "$VENV_UVICORN" ]]; then
    echo "$VENV_UVICORN"
    return
  fi
  if command -v uvicorn >/dev/null 2>&1; then
    command -v uvicorn
    return
  fi
  echo "[ERROR] 未找到 uvicorn，请先: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
}

do_start() {
  if is_running; then
    echo "[INFO] 已在运行 (PID $(cat "$PID_FILE"))，访问 http://${HOST}:${PORT}"
    exit 0
  fi

  local uvicorn_bin
  uvicorn_bin="$(resolve_uvicorn)"
  ensure_run_dir

  echo "[INFO] 启动墨记 Blog → http://${HOST}:${PORT}"
  nohup "$uvicorn_bin" app:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers 1 \
    >>"$LOG_FILE" 2>&1 &

  echo $! >"$PID_FILE"
  sleep 1

  if is_running; then
    echo "[OK] PID $(cat "$PID_FILE")，日志: $LOG_FILE"
  else
    echo "[ERROR] 启动失败，请查看日志: $LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
}

do_stop() {
  if ! is_running; then
    echo "[INFO] 未在运行"
    rm -f "$PID_FILE"
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  echo "[INFO] 停止 PID $pid ..."
  kill "$pid" 2>/dev/null || true

  for _ in $(seq 1 10); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "[OK] 已停止"
      return 0
    fi
    sleep 0.5
  done

  echo "[WARN] 强制结束 PID $pid"
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "[OK] 已停止"
}

do_restart() {
  do_stop
  do_start
}

do_status() {
  if is_running; then
    echo "[RUNNING] PID $(cat "$PID_FILE")  http://${HOST}:${PORT}"
    echo "日志: $LOG_FILE"
  else
    echo "[STOPPED]"
    rm -f "$PID_FILE"
    exit 1
  fi
}

usage() {
  cat <<EOF
用法: $0 [start|stop|restart|status]

  start    启动服务（默认）
  stop     停止服务
  restart  重启服务
  status   查看状态

环境变量:
  MOJI_HOST  监听地址（默认 0.0.0.0，可用 IP:端口 访问）
  MOJI_PORT  端口（默认 8000）
EOF
}

ACTION="${1:-start}"
case "$ACTION" in
  start) do_start ;;
  stop) do_stop ;;
  restart) do_restart ;;
  status) do_status ;;
  -h|--help|help) usage ;;
  *)
    echo "[ERROR] 未知参数: $ACTION" >&2
    usage
    exit 1
    ;;
esac
