#!/usr/bin/env bash
# Hikari — HELIOS Autonomous Coding Swarm CLI (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR/ai-router"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Silent check for remote node
python -c "from core.ai_pc_manager import ensure_ai_pc_ready; ensure_ai_pc_ready()" 2>/dev/null || true

exec python helios_code.py "$@"
