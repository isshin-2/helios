@echo off
title HELIOS Developer Edition — Router (:8000) ^& Hikari Swarm (:8001)
setlocal
cd /d "%~dp0"

echo ==============================================================================
echo   HELIOS DEVELOPER EDITION
echo   - HELIOS Core Router  : http://localhost:8000
echo   - Hikari Coding Swarm : http://localhost:8001 (WS: /ws/hikari)
echo   - Terminal CLI        : Run 'hikari.bat'
echo ==============================================================================

set "PY_EXE=ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

:: Check Budget Hardware Warning
"%PY_EXE%" -c "import sys; sys.path.insert(0, 'ai-router'); from core.hardware_governor import HardwareGovernor; print(HardwareGovernor().get_advisory_banner())"

:: Start Hikari Swarm Server in background
start "Hikari Coding Swarm [Port 8001]" cmd /c "%PY_EXE% engines\hikari\server.py"

:: Start HELIOS Core Router
cd ai-router
"%PY_EXE%" main.py
