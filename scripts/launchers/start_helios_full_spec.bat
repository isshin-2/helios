@echo off
title HELIOS — Full Spec Version (Core :8000 + Character :8080)
echo ============================================================================
echo   HELIOS — FULL SPEC VERSION
echo   1. HELIOS Core AI Router + Sandbox + Tools + Desktop UI (http://localhost:8000)
echo   2. HELIOS 3D VRM Character Presentation Add-On          (http://localhost:8080)
echo ============================================================================
echo.
set "HELIOS_EDITION=full_spec"
set "HELIOS_CHARACTER_MODE=full_spec"

:: Ensure AI PC Workstation is reachable if configured (sends native UDP WoL)
set "PY_EXE=%~dp0ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"
"%PY_EXE%" -c "from core.ai_pc_manager import ensure_ai_pc_ready; ensure_ai_pc_ready()" 2>nul

:: Launch the 3D Character Server (:8080) in Full Spec mode in a separate window
start "HELIOS Character Add-On (:8080)" cmd /c "cd /d "%~dp0helios-character" && set HELIOS_EDITION=full_spec && "%PY_EXE%" ai_server.py"

:: Open the Character Viewer in default browser after a brief delay
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8080?edition=full_spec"

:: Start HELIOS Core AI Router (:8000)
cd /d "%~dp0ai-router"
call start.bat
