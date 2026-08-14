#!/usr/bin/env bash
# Documenta los servicios de Fase 1 y comprueba el indicador de correcto
# funcionamiento de cada uno. Pensado tanto para uso manual (después de
# `scripts/setup.sh up` o `docker compose up`) como para un smoke-test en CI.
#
# Uso: scripts/healthcheck.sh
# Salida: 0 si todos los servicios obligatorios responden, 1 si alguno falla.
# Variables de entorno opcionales: BACKEND_PORT (default 8000),
# FRONTEND_PORT (default 5173), DMR_PORT (default 12434).

set -uo pipefail  # sin -e: seguimos comprobando aunque un servicio falle

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
DMR_PORT="${DMR_PORT:-12434}"

if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_FAIL=$'\033[31m'; C_BOLD=$'\033[1m'; C_RESET=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_FAIL=""; C_BOLD=""; C_RESET=""
fi

exit_code=0

# check <nombre> <url> <indicador de correcto funcionamiento> <substring esperado o ""> <required|optional>
check() {
  local name="$1" url="$2" descripcion="$3" expect="$4" required="$5"
  local response

  printf "%s%-32s%s %s\n" "$C_BOLD" "$name" "$C_RESET" "$url"
  printf "  indicador: %s\n" "$descripcion"

  if response="$(curl -sf -m 3 "$url" 2>/dev/null)"; then
    if [ -z "$expect" ] || printf '%s' "$response" | grep -q "$expect"; then
      printf "  %s[ OK ]%s responde según lo esperado\n\n" "$C_OK" "$C_RESET"
    else
      printf "  %s[WARN]%s responde pero no como se esperaba: %s\n\n" "$C_WARN" "$C_RESET" "$response"
      [ "$required" = "required" ] && exit_code=1
    fi
  else
    if [ "$required" = "required" ]; then
      printf "  %s[FAIL]%s sin respuesta\n\n" "$C_FAIL" "$C_RESET"
      exit_code=1
    else
      printf "  %s[WARN]%s sin respuesta (opcional en esta etapa)\n\n" "$C_WARN" "$C_RESET"
    fi
  fi
}

echo "== Servicios de Fase 1 =="
echo

check "Backend (FastAPI)" \
  "http://localhost:${BACKEND_PORT}/health" \
  'GET /health devuelve 200 con {"status":"ok"}' \
  '"status":"ok"' \
  required

check "Frontend (Vite dev server)" \
  "http://localhost:${FRONTEND_PORT}/" \
  "GET / devuelve 200 (HTML de la SPA)" \
  "" \
  required

check "Docker Model Runner (DMR)" \
  "http://localhost:${DMR_PORT}/engines/llama.cpp/v1/models" \
  "GET /engines/llama.cpp/v1/models devuelve 200 con la lista de modelos cargados — opcional hasta WP-6b (análisis con modelo)" \
  "" \
  optional

if [ "$exit_code" -eq 0 ]; then
  echo "${C_OK}Todos los servicios obligatorios responden.${C_RESET}"
else
  echo "${C_FAIL}Algún servicio obligatorio no responde — ver detalle arriba.${C_RESET}"
fi

exit "$exit_code"
