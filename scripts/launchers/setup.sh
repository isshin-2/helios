#!/usr/bin/env bash
# HELIOS — Unified Setup Launcher (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR/ai-router"

exec bash setup.sh "$@"
