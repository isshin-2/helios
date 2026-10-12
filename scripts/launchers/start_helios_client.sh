#!/usr/bin/env bash
# HELIOS Client Suite Launcher (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PY_BIN="python"
if [ -f "$SCRIPT_DIR/ai-router/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/ai-router/venv/bin/activate"
elif command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
fi

MODE="${1:-menu}"

case "$MODE" in
    gui|desktop)
        echo "[*] Launching HELIOS Desktop Client GUI..."
        shift || true
        exec "$PY_BIN" helios-client/main.py --gui "$@"
        ;;
    cli|terminal)
        echo "[*] Launching HELIOS Hikari Interactive Terminal..."
        shift || true
        exec "$PY_BIN" helios-client/main.py --cli "$@"
        ;;
    sidecar|daemon)
        echo "[*] Starting HELIOS Client Sidecar Daemon..."
        shift || true
        exec "$PY_BIN" helios-client/main.py --sidecar "$@"
        ;;
    status|ping)
        shift || true
        exec "$PY_BIN" helios-client/main.py --status "$@"
        ;;
    wake)
        shift || true
        exec "$PY_BIN" helios-client/main.py --wake "$@"
        ;;
    all)
        echo "[*] Launching Full Client Suite (Sidecar + GUI)..."
        "$PY_BIN" helios-client/main.py --sidecar &
        sleep 1
        exec "$PY_BIN" helios-client/main.py --gui
        ;;
    *)
        echo "============================================================================"
        echo "  HELIOS CLIENT — REMOTE CLIENT SUITE (macOS / Linux)"
        echo "============================================================================"
        echo "  [1] HELIOS Desktop Client (GUI)"
        echo "  [2] HELIOS Hikari Terminal (CLI)"
        echo "  [3] Client Sidecar Daemon Only"
        echo "  [4] Full Client Suite (GUI + Sidecar)"
        echo "  [5] Test Server Reachability & Latency Ping"
        echo "  [6] Send Wake-on-LAN to AI PC"
        echo "============================================================================"
        read -r -p "Select client mode [1-6, default=1]: " CHOICE
        case "$CHOICE" in
            2) exec "$PY_BIN" helios-client/main.py --cli ;;
            3) exec "$PY_BIN" helios-client/main.py --sidecar ;;
            4)
                "$PY_BIN" helios-client/main.py --sidecar &
                sleep 1
                exec "$PY_BIN" helios-client/main.py --gui
                ;;
            5) exec "$PY_BIN" helios-client/main.py --status ;;
            6) exec "$PY_BIN" helios-client/main.py --wake ;;
            *) exec "$PY_BIN" helios-client/main.py --gui ;;
        esac
        ;;
esac
