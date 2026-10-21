#!/usr/bin/env bash
# HELIOS Server Runner (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "[!] Virtual environment not found. Running setup..."
    bash setup.sh --quick
    source venv/bin/activate
fi

# Run setup if first time
if [ ! -f ".setup_complete" ]; then
    python setup.py
fi

SERVER_PORT="${SERVER_PORT:-8000}"

echo "======================================================="
echo "   HELIOS Server Starting..."
echo "   Local UI: http://localhost:$SERVER_PORT"
echo "======================================================="
exec python -m uvicorn main:app --host 0.0.0.0 --port "$SERVER_PORT"
