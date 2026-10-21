#!/usr/bin/env python3
"""HELIOS — Root Forwarder Entrypoint.
Delegates directly to scripts/launchers/helios.py.
"""
import os
import sys
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parent / "scripts" / "launchers" / "helios.py"
if LAUNCHER.exists():
    with open(LAUNCHER, "r", encoding="utf-8") as f:
        code = compile(f.read(), str(LAUNCHER), "exec")
        exec(code, {"__name__": "__main__", "__file__": str(LAUNCHER)})
else:
    print(f"[!] Error: Launcher script not found at {LAUNCHER}")
    sys.exit(1)
