@echo off
title HELIOS Client Launcher
setlocal enabledelayedexpansion

set "PY_EXE=%~dp0..\..\ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

:: Command-line argument routing
if /i "%~1"=="gui" goto run_gui
if /i "%~1"=="desktop" goto run_gui
if /i "%~1"=="cli" goto run_cli
if /i "%~1"=="terminal" goto run_cli
if /i "%~1"=="sidecar" goto run_sidecar
if /i "%~1"=="daemon" goto run_sidecar
if /i "%~1"=="all" goto run_all
if /i "%~1"=="status" goto run_status
if /i "%~1"=="ping" goto run_status
if /i "%~1"=="wake" goto run_wake
if /i "%~1"=="airi" goto run_airi

:menu
cls
echo ============================================================================
echo   HELIOS CLIENT — REMOTE CLIENT SUITE
echo   Connects to HELIOS Core Server (Local / NVIDIA PAIR / Remote Server)
echo ============================================================================
echo.
echo   [1] HELIOS Desktop Client (GUI) — Cyberpunk HUD + Server Switcher + Sidecar
echo   [2] HELIOS Hikari Terminal (CLI) — Claude Code / Codex Remote Console
echo   [3] Client Sidecar Daemon Only — Connects client OS, Screen & Shell to Server
echo   [4] Full Client Suite — Desktop App + Sidecar Daemon
echo   [5] Test Server Reachability & Latency Ping
echo   [6] Send Wake-on-LAN to NVIDIA PAIR Node
echo   [7] Launch Airi 3D Avatar (Connected to Remote Server)
echo ============================================================================
set /p "CHOICE=Select client mode [1-7, default=1]: "

if "%CHOICE%"=="2" goto run_cli
if "%CHOICE%"=="3" goto run_sidecar
if "%CHOICE%"=="4" goto run_all
if "%CHOICE%"=="5" goto run_status
if "%CHOICE%"=="6" goto run_wake
if "%CHOICE%"=="7" goto run_airi
goto run_gui

:run_gui
echo [*] Launching HELIOS Desktop Client GUI...
cd /d "%~dp0..\.."
if not "%~1"=="" shift
"%PY_EXE%" helios-client\main.py --gui %1 %2 %3 %4 %5
goto :eof

:run_cli
echo [*] Launching HELIOS Hikari Interactive Terminal...
cd /d "%~dp0..\.."
if not "%~1"=="" shift
"%PY_EXE%" helios-client\main.py --cli %1 %2 %3 %4 %5
goto :eof

:run_sidecar
echo [*] Starting HELIOS Client Sidecar Daemon...
cd /d "%~dp0..\.."
if not "%~1"=="" shift
"%PY_EXE%" helios-client\main.py --sidecar %1 %2 %3 %4 %5
goto :eof

:run_all
echo [*] Launching Full Client Suite (Sidecar + Desktop GUI)...
cd /d "%~dp0..\.."
start "HELIOS Sidecar" cmd /c ""%PY_EXE%" helios-client\main.py --sidecar"
timeout /t 1 /nobreak >nul
"%PY_EXE%" helios-client\main.py --gui
goto :eof

:run_status
echo [*] Testing server connectivity...
cd /d "%~dp0..\.."
set "WAS_ARG=%~1"
if not "%~1"=="" shift
"%PY_EXE%" helios-client\main.py --status %1 %2 %3 %4 %5
echo.
if not "!WAS_ARG!"=="" goto :eof
pause
goto menu

:run_wake
echo [*] Transmitting Wake-on-LAN packet to NVIDIA PAIR Node...
cd /d "%~dp0..\.."
set "WAS_ARG=%~1"
if not "%~1"=="" shift
"%PY_EXE%" helios-client\main.py --wake %1 %2 %3 %4 %5
echo.
if not "!WAS_ARG!"=="" goto :eof
pause
goto menu

:run_airi
echo [*] Launching Airi 3D Avatar connected to remote server...
call "%~dp0start_airi.bat"
goto :eof
