#!/usr/bin/env bash
# Airi — 3D Cybernetic Presentation Companion (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR/helios-character"

PY_BIN="python"
if [ -f "$ROOT_DIR/ai-router/venv/bin/activate" ]; then
    source "$ROOT_DIR/ai-router/venv/bin/activate"
    PY_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
fi

export HELIOS_EDITION="full_spec"
export HELIOS_CHARACTER_MODE="full_spec"

# Open browser in background after short delay
(
    sleep 2
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:8080?edition=full_spec" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
        open "http://localhost:8080?edition=full_spec" >/dev/null 2>&1 || true
    fi
) &

exec "$PY_BIN" ai_server.py
