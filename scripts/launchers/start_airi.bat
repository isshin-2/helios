@echo off
setlocal enabledelayedexpansion
title AIRI — 3D Cybernetic Companion
echo ============================================================================
echo   AIRI -- 3D CYBERNETIC COMPANION -- On-Demand Visual Interface
echo   Connects to HELIOS Core on AI PC or Localhost on port 8000
echo ============================================================================
echo.

:: Detect configured server endpoint (from .env or default)
set "TARGET_HOST=localhost"
set "TARGET_PORT=8000"
if exist "%~dp0ai-router\.env" (
    for /f "tokens=1,2 delims==" %%A in ('type "%~dp0ai-router\.env"') do (
        if /i "%%A"=="AI_PC_IP" set "TARGET_HOST=%%B"
        if /i "%%A"=="SERVER_PORT" set "TARGET_PORT=%%B"
    )
)

set "HELIOS_CORE_URL=http://localhost:!TARGET_PORT!"
if not "!TARGET_HOST!"=="localhost" if not "!TARGET_HOST!"=="127.0.0.1" (
    powershell -NoProfile -Command "if (Test-NetConnection -ComputerName !TARGET_HOST! -Port !TARGET_PORT! -InformationLevel Quiet -WarningAction SilentlyContinue) { exit 0 } else { exit 1 }"
    if !ERRORLEVEL! equ 0 (
        set "HELIOS_CORE_URL=http://!TARGET_HOST!:!TARGET_PORT!"
        echo [*] Connected to HELIOS Core on remote node: !HELIOS_CORE_URL!
    ) else (
        echo [*] Remote node !TARGET_HOST! is offline. Connecting to local HELIOS Core: !HELIOS_CORE_URL!
    )
) else (
    echo [*] Connecting to local HELIOS Core: !HELIOS_CORE_URL!
)

set "HELIOS_EDITION=full_spec"
set "HELIOS_CHARACTER_MODE=full_spec"

cd /d "%~dp0helios-character"

set "PY_EXE=%~dp0ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

:: Open the 3D Character in default browser
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8080?edition=full_spec"

:: Run the companion server
"%PY_EXE%" ai_server.py
pause
