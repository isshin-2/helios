@echo off
title HELIOS Core Server — AI PC Workstation (0.0.0.0:8000)
echo ============================================================================
echo   HELIOS CORE AI SERVER (AI PC Workstation)
echo   Hardware: RTX 5060 Ti (16 GB VRAM) + 64 GB DDR5 RAM
echo   Network Address: http://192.168.100.254:8000 (0.0.0.0:8000)
echo ============================================================================
echo.

cd /d "%~dp0..\ai-router"

set "PY_EXE=venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

echo [*] Starting HELIOS Core on port 8000 (accessible across LAN)...
echo [*] From your laptop:
echo     - Web Interface : http://192.168.100.254:8000
echo     - Hikari CLI    : Run '.\hikari.bat' on your laptop
echo     - Airi (Avatar) : Run '.\start_airi.bat' when you want company
echo.

"%PY_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
