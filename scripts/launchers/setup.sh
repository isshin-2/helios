#!/usr/bin/env bash
# HELIOS — Unified Setup Launcher (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/ai-router"

exec bash setup.sh "$@"
