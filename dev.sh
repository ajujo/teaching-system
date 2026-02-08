#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$PROJECT_ROOT/web"

PIDS_DIR="$PROJECT_ROOT/.pids"
LOGS_DIR="$PROJECT_ROOT/.logs"
BACK_PID="$PIDS_DIR/backend.pid"
FRONT_PID="$PIDS_DIR/frontend.pid"

BACK_PORT=8000
FRONT_PORT=3000

mkdir -p "$PIDS_DIR" "$LOGS_DIR"

is_listening() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

pid_running() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

kill_pidfile() {
  local pidfile="$1"
  local name="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile" || true)"
    if [[ -n "${pid:-}" ]] && pid_running "$pid"; then
      echo "→ Parando $name (PID $pid)..."
      kill "$pid" >/dev/null 2>&1 || true

      # Espera hasta 3s a que muera
      for _ in {1..30}; do
        if ! pid_running "$pid"; then break; fi
        sleep 0.1
      done

      # Si sigue vivo, fuerza
      if pid_running "$pid"; then
        echo "  ⚠️  $name no se paró, forzando (kill -9)..."
        kill -9 "$pid" >/dev/null 2>&1 || true
      fi
    fi
    rm -f "$pidfile"
  fi
}

kill_port() {
  local port="$1"
  local name="$2"
  if is_listening "$port"; then
    echo "→ Matando procesos escuchando en $port ($name)..."
    # Primero suave
    local pids
    pids="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      kill $pids >/dev/null 2>&1 || true
      sleep 0.5
      # Si queda alguien, fuerza
      pids="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$pids" ]]; then
        kill -9 $pids >/dev/null 2>&1 || true
      fi
    fi
  fi
}

check_port_conflict() {
  local port="$1"
  local pidfile="$2"
  local name="$3"

  if is_listening "$port"; then
    local listening_pids
    listening_pids="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"

    if [[ -f "$pidfile" ]]; then
      local saved_pid
      saved_pid="$(cat "$pidfile" || true)"
      # Check if our saved PID matches what's listening
      if [[ -n "$saved_pid" ]] && echo "$listening_pids" | grep -qw "$saved_pid"; then
        echo "  ⚠️  $name ya está corriendo (PID $saved_pid)"
        return 1
      fi
    fi

    # Port is taken by something else
    echo "❌ Puerto $port ya en uso por proceso(s): $listening_pids"
    echo "   Para ver detalles: lsof -i :$port"
    echo "   Para liberar: kill \$(lsof -t -iTCP:$port -sTCP:LISTEN)"
    return 2
  fi
  return 0
}

start_backend() {
  echo "🚀 Arrancando backend (uvicorn) en :$BACK_PORT..."

  # Check if already running by our PID
  if [[ -f "$BACK_PID" ]]; then
    local pid
    pid="$(cat "$BACK_PID" || true)"
    if [[ -n "$pid" ]] && pid_running "$pid"; then
      echo "  ⚠️  Backend ya está corriendo (PID $pid). Usa 'restart' para reiniciar."
      return 0
    fi
    rm -f "$BACK_PID"
  fi

  # Check port conflict
  if ! check_port_conflict "$BACK_PORT" "$BACK_PID" "backend"; then
    local ret=$?
    if [[ $ret -eq 1 ]]; then return 0; fi  # Already running by us
    return 1  # Port conflict with external process
  fi

  # Arranque en background con logs
  (cd "$PROJECT_ROOT" && \
    uv run python -m uvicorn teaching.web.api:app --reload --port "$BACK_PORT" \
      >"$LOGS_DIR/backend.log" 2>&1 & echo $! >"$BACK_PID")

  echo "  ✅ Backend PID: $(cat "$BACK_PID") (logs: .logs/backend.log)"
}

start_frontend() {
  echo "🚀 Arrancando frontend (Next) en :$FRONT_PORT..."

  # Check if already running by our PID
  if [[ -f "$FRONT_PID" ]]; then
    local pid
    pid="$(cat "$FRONT_PID" || true)"
    if [[ -n "$pid" ]] && pid_running "$pid"; then
      echo "  ⚠️  Frontend ya está corriendo (PID $pid). Usa 'restart' para reiniciar."
      return 0
    fi
    rm -f "$FRONT_PID"
  fi

  # Check port conflict
  if ! check_port_conflict "$FRONT_PORT" "$FRONT_PID" "frontend"; then
    local ret=$?
    if [[ $ret -eq 1 ]]; then return 0; fi  # Already running by us
    return 1  # Port conflict with external process
  fi

  if [[ ! -d "$WEB_DIR" ]]; then
    echo "❌ No existe ./web. ¿Seguro que el frontend está en $WEB_DIR?"
    exit 1
  fi

  (cd "$WEB_DIR" && \
    npm run dev \
      >"$LOGS_DIR/frontend.log" 2>&1 & echo $! >"$FRONT_PID")

  echo "  ✅ Frontend PID: $(cat "$FRONT_PID") (logs: .logs/frontend.log)"
}

status() {
  echo "=== STATUS ==="
  if [[ -f "$BACK_PID" ]]; then
    local pid; pid="$(cat "$BACK_PID")"
    if pid_running "$pid"; then
      echo "Backend: RUNNING (PID $pid)  port:$BACK_PORT"
    else
      echo "Backend: NOT RUNNING (pidfile existe pero PID muerto)"
    fi
  else
    echo "Backend: NOT RUNNING"
  fi

  if [[ -f "$FRONT_PID" ]]; then
    local pid; pid="$(cat "$FRONT_PID")"
    if pid_running "$pid"; then
      echo "Frontend: RUNNING (PID $pid)  port:$FRONT_PORT"
    else
      echo "Frontend: NOT RUNNING (pidfile existe pero PID muerto)"
    fi
  else
    echo "Frontend: NOT RUNNING"
  fi

  echo ""
  echo "Puertos:"
  echo "  8000 -> $(is_listening 8000 && echo LISTENING || echo free)"
  echo "  3000 -> $(is_listening 3000 && echo LISTENING || echo free)"
}

stop_all() {
  echo "🛑 Parando servicios..."
  # Para por pidfile primero (limpio)
  kill_pidfile "$FRONT_PID" "frontend"
  kill_pidfile "$BACK_PID"  "backend"

  # Si queda algo colgado, limpia por puerto
  kill_port "$FRONT_PORT" "frontend"
  kill_port "$BACK_PORT"  "backend"

  echo "  ✅ Parado. (logs en .logs/)"
}

tail_logs() {
  echo "📜 Logs (Ctrl+C para salir)"
  touch "$LOGS_DIR/backend.log" "$LOGS_DIR/frontend.log"
  tail -n 200 -f "$LOGS_DIR/backend.log" "$LOGS_DIR/frontend.log"
}

case "${1:-}" in
  start)
    start_backend
    start_frontend
    echo ""
    echo "✅ Todo arrancado:"
    echo "  Backend:  http://localhost:$BACK_PORT/docs"
    echo "  Frontend: http://localhost:$FRONT_PORT"
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_backend
    start_frontend
    ;;
  status)
    status
    ;;
  logs)
    tail_logs
    ;;
  *)
    echo "Uso: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
