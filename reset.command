#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"
echo "=========================================="
echo "   HELIOS Factory Reset Utility"
echo "=========================================="
echo "This will allow you to reconfigure HELIOS."
echo ""
python3 setup.py --reset
echo ""
echo "Reset complete. Run ./start.command to launch HELIOS."
read -p "Press Enter to exit..."
