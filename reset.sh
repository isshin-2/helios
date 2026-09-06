#!/bin/bash
echo "=========================================="
echo "   HELIOS Factory Reset Utility"
echo "=========================================="
echo "This will allow you to reconfigure HELIOS."
echo ""
python3 setup.py --reset
echo ""
echo "Reset complete. Run ./start.sh to launch HELIOS."
