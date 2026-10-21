#!/usr/bin/env bash
# HELIOS — Master Ecosystem Launcher (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

CHOICE="${1:-}"

if [ -z "$CHOICE" ]; then
    echo "============================================================================"
    echo "  HELIOS — AUTONOMOUS AI & CODING ECOSYSTEM (macOS / Linux)"
    echo "  Main System: HELIOS (Swarm, Model Router, Tools, Knowledge Memory)"
    echo "  Companion  : Airi (3D VRM Visual Avatar — Launched On-Demand)"
    echo "============================================================================"
    echo ""
    echo "  [1] HELIOS Core Server   (Main AI Router :8000, Swarm, RAG, Hardware Arbitrator)"
    echo "  [2] Hikari Coding CLI    (hikari.sh — Interactive Claude Code / Codex Terminal)"
    echo "  [3] HELIOS + Airi        (Core Server :8000 + Airi 3D Companion :8080)"
    echo "  [4] Airi Companion Only  (Standalone 3D VRM Character without :8000)"
    echo "  [5] Mobile Phone App     (start_phone.sh — Expo Go Android / iOS :8081)"
    echo "  [6] HELIOS Client Mode   (start_helios_client.sh — Connect to Server / NVIDIA PAIR)"
    echo "  [7] Environment Setup    (setup.sh — Dependencies, venv & configuration)"
    echo "============================================================================"
    read -r -p "Select launch mode [1-7, default=1]: " CHOICE
fi

case "$CHOICE" in
    1|core|main|server|router)
        echo "[*] Starting HELIOS Core AI Router (:8000)..."
        cd "$ROOT_DIR/ai-router"
        exec bash start.sh
        ;;
    2|hikari)
        exec bash "$SCRIPT_DIR/hikari.sh"
        ;;
    3|full|airi_full)
        exec bash "$SCRIPT_DIR/start_helios_full_spec.sh"
        ;;
    4|char|airi)
        exec bash "$SCRIPT_DIR/start_airi.sh"
        ;;
    5|phone|mobile)
        exec bash "$SCRIPT_DIR/start_phone.sh"
        ;;
    6|client)
        exec bash "$SCRIPT_DIR/start_helios_client.sh"
        ;;
    7|setup)
        exec bash "$SCRIPT_DIR/setup.sh"
        ;;
    *)
        echo "[*] Starting HELIOS Core AI Router (:8000)..."
        cd "$ROOT_DIR/ai-router"
        exec bash start.sh
        ;;
esac
