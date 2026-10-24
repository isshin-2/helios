@echo off
title HELIOS — Just the Character (Standalone 3D VRM Edition :8080)
echo ============================================================================
echo   HELIOS — JUST THE CHARACTER (STANDALONE EDITION)
echo   - 3D VRM / Live2D Viewer     : http://localhost:8080?edition=character_only
echo   - Standalone Character Brain : Local Ollama Chat + Neural TTS + Lip-Sync
echo   - 3D Body & Pose Engine      : 24 Human Poses + 6 Styles + RL Pose Trainer
echo   - Lightweight Mode           : Runs WITHOUT starting ai-router (:8000)
echo ============================================================================
echo.

set "HELIOS_EDITION=character_only"
set "HELIOS_CHARACTER_MODE=character_only"

cd /d "%~dp0"

set "PY_EXE=%~dp0..\ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8080?edition=character_only"
"%PY_EXE%" ai_server.py
pause
