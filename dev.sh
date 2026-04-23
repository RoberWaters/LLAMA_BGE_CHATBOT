#!/usr/bin/env bash
# dev.sh - Arranca backend (FastAPI :8000) y frontend (Vite :3000) en paralelo.
# Comandos: r reiniciar   s estado   q salir   (tambien Ctrl+C)

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/venv/bin/python"

BACKEND_PID=""
FRONTEND_PID=""

# Colores
R='\033[0;31m'
G='\033[0;32m'
Y='\033[1;33m'
B='\033[0;34m'
C='\033[0;36m'
N='\033[0m'
BD='\033[1m'

# --------------------------------------------------------------------------- #

kill_proc() {
    local pid="$1"
    [[ -z "$pid" ]] && return
    if kill -0 "$pid" 2>/dev/null; then
        pkill -P "$pid" 2>/dev/null || true   # mata hijos (p.ej. vite lanzado por npm)
        kill "$pid"    2>/dev/null || true
        wait "$pid"    2>/dev/null || true
    fi
}

start_backend() {
    echo -e "${B}Backend${N}  - http://localhost:8000  (docs: http://localhost:8000/docs)"
    (cd "$PROJECT_DIR" && "$PYTHON" api/main.py) &
    BACKEND_PID=$!
}

start_frontend() {
    echo -e "${C}Frontend${N} - http://localhost:3000"
    (cd "$PROJECT_DIR/frontend" && npm run dev) &
    FRONTEND_PID=$!
}

stop_servers() {
    kill_proc "$BACKEND_PID"
    kill_proc "$FRONTEND_PID"
    BACKEND_PID=""
    FRONTEND_PID=""
}

restart_servers() {
    echo -e "\n${Y}Reiniciando servidores...${N}"
    stop_servers
    sleep 1
    start_backend
    start_frontend
    echo -e "${G}Listo.${N}\n"
}

print_status() {
    local b="${R}detenido${N}"
    local f="${R}detenido${N}"
    [[ -n "$BACKEND_PID"  ]] && kill -0 "$BACKEND_PID"  2>/dev/null && b="${G}corriendo${N} (pid $BACKEND_PID)"
    [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null && f="${G}corriendo${N} (pid $FRONTEND_PID)"
    echo -e "  Backend:  $b"
    echo -e "  Frontend: $f"
}

cleanup() {
    echo -e "\n${Y}Apagando servidores...${N}"
    stop_servers
    echo -e "${R}Servidores detenidos.${N}"
    exit 0
}

# --------------------------------------------------------------------------- #

if [[ ! -x "$PYTHON" ]]; then
    echo -e "${R}Error:${N} venv no encontrado en $PROJECT_DIR/venv"
    echo "Crea el entorno virtual primero:"
    echo "  python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

trap cleanup SIGINT SIGTERM

echo -e "\n${BD}VOAE Chatbot - Dev${N}"
echo "--------------------------------"
start_backend
start_frontend
echo ""
echo -e "${BD}Comandos:${N}  ${Y}r${N} reiniciar   ${Y}s${N} estado   ${Y}q${N} salir"
echo ""

while true; do
    read -r cmd || cleanup
    case "${cmd,,}" in
        r) restart_servers ;;
        s) print_status    ;;
        q) cleanup         ;;
        "") ;;
        *) echo -e "${Y}Comandos:${N}  r reiniciar   s estado   q salir" ;;
    esac
done
