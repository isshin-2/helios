#!/usr/bin/env bash
# HELIOS Engineering Portfolio Launcher (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "  HELIOS ENGINEERING PORTFOLIO (Vite + React 19)"
echo "======================================================================"

if ! command -v node >/dev/null 2>&1; then
    echo "[ERROR] Node.js is not installed or not in PATH!"
    exit 1
fi

if [ ! -d "node_modules" ]; then
    echo "[*] Installing node dependencies..."
    npm install
fi

echo "[*] Launching Portfolio on http://localhost:5174..."
(
    sleep 2
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:5174" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
        open "http://localhost:5174" >/dev/null 2>&1 || true
    fi
) &

exec npm run dev
