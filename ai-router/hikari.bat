@echo off
title Hikari — HELIOS Autonomous Coding Swarm
setlocal

set "PY_EXE=venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

:: Silent headless check for NVIDIA PAIR reachability (sends native UDP WoL if sleeping)
"%PY_EXE%" -c "from core.ai_pc_manager import ensure_ai_pc_ready; ensure_ai_pc_ready()" 2>nul

:: Launch Hikari CLI
"%PY_EXE%" helios_code.py %*
