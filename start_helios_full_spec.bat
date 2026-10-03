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

:: Verify AI PC is reachable; if offline, run wake script
powershell -NoProfile -Command "if (-not (Test-NetConnection -ComputerName 192.168.100.254 -Port 3389 -InformationLevel Quiet -WarningAction SilentlyContinue)) { Write-Host '[HELIOS] AI PC is offline. Launching AI-PC.ps1 wake script...' -ForegroundColor Yellow; Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"C:\Users\krithik\Desktop\AI-PC.ps1\"' }"

:: Launch the 3D Character Server (:8080) in Full Spec mode in a separate window
start "HELIOS Character Add-On (:8080)" cmd /c "cd /d "%~dp0helios-character" && set HELIOS_EDITION=full_spec && call start_vrm_addon.bat"

:: Open the Character Viewer in default browser after a brief delay
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8080?edition=full_spec"

:: Start HELIOS Core AI Router (:8000)
cd /d "%~dp0ai-router"
call start.bat
