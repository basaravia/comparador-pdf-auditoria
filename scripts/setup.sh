#!/usr/bin/env bash
# Prerrequisitos + arranque de los servicios de Fase 1 (backend FastAPI +
# frontend Vite) en local, sin Docker. Para correr todo en contenedores usar
# `docker compose up --build` (ver la nota sobre DMR en docker-compose.yml).
#
# Uso:
#   scripts/setup.sh check   # solo comprueba prerrequisitos, no instala ni levanta nada
#   scripts/setup.sh up      # comprueba, instala dependencias y levanta backend + frontend (default)
#   scripts/setup.sh down    # detiene los servicios levantados por este script
#   scripts/setup.sh status  # atajo a scripts/healthcheck.sh
#
# Variables de entorno opcionales: BACKEND_PORT (default 8000),
# FRONTEND_PORT (default 5173).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$REPO_ROOT/.run"

# Precedencia: variable de entorno explícita > backend/.env > default. Se
# guarda aquí porque `source backend/.env` (en start_backend) reasignaría
# BACKEND_PORT incondicionalmente y pisaría un override pasado por el caller.
BACKEND_PORT_OVERRIDE="${BACKEND_PORT:-}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_FAIL=$'\033[31m'; C_RESET=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_FAIL=""; C_RESET=""
fi
ok()   { printf "  %s[ OK ]%s %s\n"   "$C_OK"   "$C_RESET" "$1"; }
warn() { printf "  %s[WARN]%s %s\n"   "$C_WARN" "$C_RESET" "$1"; }
fail() { printf "  %s[FAIL]%s %s\n"   "$C_FAIL" "$C_RESET" "$1"; }
log()  { printf "\n== %s ==\n" "$1"; }

check_prereqs() {
  log "Prerrequisitos"
  local missing=0

  if command -v uv >/dev/null 2>&1; then
    ok "uv $(uv --version | awk '{print $2}')"
  else
    fail "uv no encontrado — instalar: https://docs.astral.sh/uv/getting-started/installation/"
    missing=1
  fi

  if command -v node >/dev/null 2>&1; then
    local node_major
    node_major="$(node --version | sed 's/^v//' | cut -d. -f1)"
    if [ "$node_major" -ge 20 ]; then
      ok "node $(node --version)"
    else
      warn "node $(node --version) encontrado — se recomienda Node 20+"
    fi
  else
    fail "node no encontrado — instalar Node 20+: https://nodejs.org/"
    missing=1
  fi

  if command -v npm >/dev/null 2>&1; then
    ok "npm $(npm --version)"
  else
    fail "npm no encontrado (normalmente viene con node)"
    missing=1
  fi

  if command -v docker >/dev/null 2>&1; then
    ok "docker $(docker --version | awk '{print $3}' | tr -d ,) — opcional, solo para 'docker compose up'"
  else
    warn "docker no encontrado — opcional, solo necesario para correr todo en contenedores"
  fi

  if curl -sf -m 2 "http://localhost:12434/engines/llama.cpp/v1/models" >/dev/null 2>&1; then
    ok "Docker Model Runner responde en :12434"
  else
    warn "Docker Model Runner no responde en :12434 — opcional en WP-0/WP-1, necesario desde WP-6b"
  fi

  if [ "$missing" -ne 0 ]; then
    echo
    fail "Faltan prerrequisitos obligatorios. Instalar lo indicado arriba y reintentar."
    exit 1
  fi
}

ensure_env_files() {
  if [ -f "$REPO_ROOT/backend/.env.example" ] && [ ! -f "$REPO_ROOT/backend/.env" ]; then
    cp "$REPO_ROOT/backend/.env.example" "$REPO_ROOT/backend/.env"
    warn "creado backend/.env desde .env.example"
  fi
  if [ -f "$REPO_ROOT/frontend/.env.example" ] && [ ! -f "$REPO_ROOT/frontend/.env" ]; then
    cp "$REPO_ROOT/frontend/.env.example" "$REPO_ROOT/frontend/.env"
    warn "creado frontend/.env desde .env.example"
  fi
}

install_deps() {
  log "Instalando dependencias"
  (cd "$REPO_ROOT/backend" && uv sync --group dev)
  (cd "$REPO_ROOT/frontend" && npm install)
  (cd "$REPO_ROOT/backend" && uv run python -m comparador.schemas.export)
  (cd "$REPO_ROOT/frontend" && node scripts/generate-types.mjs)
}

is_running() {
  local pid_file="$RUN_DIR/$1.pid"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1 && { exec 3>&-; return 0; }
  return 1
}

start_backend() {
  if is_running backend; then
    warn "backend ya está corriendo (PID $(cat "$RUN_DIR/backend.pid"))"
    return
  fi
  if [ -f "$REPO_ROOT/backend/.env" ]; then
    set -a; source "$REPO_ROOT/backend/.env"; set +a
  fi
  BACKEND_PORT="${BACKEND_PORT_OVERRIDE:-$BACKEND_PORT}"
  if port_in_use "$BACKEND_PORT"; then
    fail "el puerto $BACKEND_PORT ya está en uso por otro proceso — reintentar con BACKEND_PORT=<otro> scripts/setup.sh up"
    return
  fi
  log "Levantando backend en :${BACKEND_PORT}"
  (
    cd "$REPO_ROOT/backend"
    nohup "$REPO_ROOT/backend/.venv/bin/uvicorn" comparador.main:app \
      --host "${BACKEND_HOST:-0.0.0.0}" --port "$BACKEND_PORT" \
      > "$RUN_DIR/backend.log" 2>&1 &
    echo $! > "$RUN_DIR/backend.pid"
  )
  ok "backend PID $(cat "$RUN_DIR/backend.pid") — logs en .run/backend.log"
}

start_frontend() {
  if is_running frontend; then
    warn "frontend ya está corriendo (PID $(cat "$RUN_DIR/frontend.pid"))"
    return
  fi
  if port_in_use "$FRONTEND_PORT"; then
    fail "el puerto $FRONTEND_PORT ya está en uso por otro proceso — reintentar con FRONTEND_PORT=<otro> scripts/setup.sh up"
    return
  fi
  log "Levantando frontend en :${FRONTEND_PORT}"
  (
    cd "$REPO_ROOT/frontend"
    nohup npx --no-install vite --port "$FRONTEND_PORT" --host 0.0.0.0 \
      > "$RUN_DIR/frontend.log" 2>&1 &
    echo $! > "$RUN_DIR/frontend.pid"
  )
  ok "frontend PID $(cat "$RUN_DIR/frontend.pid") — logs en .run/frontend.log"
}

wait_for_backend() {
  if ! is_running backend; then
    warn "el backend no está corriendo — nada que esperar (ver mensaje anterior)"
    return
  fi
  log "Esperando a que el backend responda"
  for _ in $(seq 1 20); do
    if curl -sf -m 1 "http://localhost:${BACKEND_PORT}/health" | grep -q '"status":"ok"'; then
      ok "backend healthy en http://localhost:${BACKEND_PORT}/health"
      return
    fi
    sleep 0.5
  done
  warn "el backend no respondió a tiempo — revisar .run/backend.log"
}

cmd_up() {
  check_prereqs
  ensure_env_files
  install_deps
  mkdir -p "$RUN_DIR"
  start_backend
  start_frontend
  wait_for_backend
  echo
  echo "Backend:  http://localhost:${BACKEND_PORT} (docs en /docs, salud en /health)"
  echo "Frontend: http://localhost:${FRONTEND_PORT}"
  echo
  echo "Para verificar el estado de los servicios: scripts/healthcheck.sh"
  echo "Para detenerlos: scripts/setup.sh down"
}

cmd_down() {
  log "Deteniendo servicios"
  for name in backend frontend; do
    local pid_file="$RUN_DIR/$name.pid"
    if [ -f "$pid_file" ]; then
      local pid
      pid="$(cat "$pid_file")"
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        ok "$name detenido (PID $pid)"
      else
        warn "$name no estaba corriendo (PID $pid obsoleto)"
      fi
      rm -f "$pid_file"
    else
      warn "$name no tiene PID registrado en .run/ — nada que detener"
    fi
  done
}

case "${1:-up}" in
  check)  check_prereqs ;;
  up)     cmd_up ;;
  down)   cmd_down ;;
  status) exec "$REPO_ROOT/scripts/healthcheck.sh" ;;
  *)
    echo "Uso: $0 {check|up|down|status}" >&2
    exit 1
    ;;
esac
