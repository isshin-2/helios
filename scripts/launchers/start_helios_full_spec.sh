#!/usr/bin/env bash
# HELIOS — Full Spec Version (Core :8000 + Airi 3D Companion :8080)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

PY_BIN="python"
if [ -f "$ROOT_DIR/ai-router/venv/bin/activate" ]; then
    source "$ROOT_DIR/ai-router/venv/bin/activate"
elif command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
fi

export HELIOS_EDITION="full_spec"
export HELIOS_CHARACTER_MODE="full_spec"

echo "============================================================================"
echo "  HELIOS — FULL SPEC ECOSYSTEM (macOS / Linux)"
echo "  1. HELIOS Core AI Router + Sandbox + Swarm    (http://localhost:8000)"
echo "  2. HELIOS Airi 3D VRM Presentation Companion  (http://localhost:8080)"
echo "============================================================================"

# Launch 3D Character Server in background
(
    cd "$ROOT_DIR/helios-character"
    "$PY_BIN" ai_server.py
) &
CHAR_PID=$!

# Open browser for Character Viewer after brief delay
(
    sleep 3
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:8080?edition=full_spec" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
        open "http://localhost:8080?edition=full_spec" >/dev/null 2>&1 || true
    fi
) &

# Ensure cleanup on exit
trap "kill $CHAR_PID 2>/dev/null || true" EXIT

# Start Core AI Router
cd "$ROOT_DIR/ai-router"
exec bash start.sh
