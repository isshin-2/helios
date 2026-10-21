#!/usr/bin/env bash
# HELIOS — Unified Setup & Configuration (macOS / Linux)
set -e

# Detect script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ANSI Colors
CYAN='\033[1;36m'
BLUE='\033[1;34m'
WHITE='\033[1;37m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
RESET='\033[0m'

echo -e "${CYAN}"
echo "   __  __  ______  _       _____   ____    _____ "
echo "  |  |/  ||  ____|| |     |_   _| / __ \  / ____|"
echo "  |      || |__   | |       | |  | |  | || (___  "
echo "  |  __  ||  __|  | |       | |  | |  | | \___ \ "
echo "  | |  | || |____ | |____  _| |_ | |__| | ____) |"
echo "  |_|  |_||______||______||_____| \____/ |_____/ "
echo -e "${RESET}"
echo -e "${BLUE}          Artificial Intelligence Router & Autonomous Swarm${RESET}\n"

# 1. Check Python
echo -e "${CYAN}[1/4] Checking Python 3.10+...${RESET}"
PY_BIN=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        PY_MAJOR=$("$cmd" -c 'import sys; print(sys.version_info.major)')
        PY_MINOR=$("$cmd" -c 'import sys; print(sys.version_info.minor)')
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PY_BIN="$cmd"
            echo -e "${GREEN}[V] Found Python: $PY_BIN ($PY_VER)${RESET}"
            break
        fi
    fi
done

if [ -z "$PY_BIN" ]; then
    echo -e "${RED}[X] Python 3.10+ is required but not found in PATH.${RESET}"
    exit 1
fi

# 2. Virtual Environment
echo -e "\n${CYAN}[2/4] Setting up Virtual Environment...${RESET}"
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${YELLOW}[*] Creating virtual environment in ./venv...${RESET}"
    "$PY_BIN" -m venv venv
    echo -e "${GREEN}[+] Virtual environment created successfully.${RESET}"
else
    echo -e "${GREEN}[V] Virtual environment already exists.${RESET}"
fi

source venv/bin/activate

# 3. Dependencies
echo -e "\n${CYAN}[3/4] Installing / Verifying Dependencies...${RESET}"
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

# 4. Interactive / Quick Setup
echo -e "\n${CYAN}[4/4] Environment Configuration...${RESET}"
python setup.py "$@"

echo -e "\n${GREEN}=======================================================${RESET}"
echo -e "${GREEN}   HELIOS Setup Complete!${RESET}"
echo -e "${WHITE}   Run ./start.sh or ../start_helios.sh to launch.${RESET}"
echo -e "${GREEN}=======================================================${RESET}"
