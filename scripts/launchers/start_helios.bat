@echo off
title HELIOS Ecosystem Launcher
setlocal

if /i "%~1"=="1" goto core_only
if /i "%~1"=="core" goto core_only
if /i "%~1"=="2" goto hikari_cli
if /i "%~1"=="hikari" goto hikari_cli
if /i "%~1"=="3" goto full_spec
if /i "%~1"=="airi" goto full_spec
if /i "%~1"=="4" goto char_only
if /i "%~1"=="5" goto mobile_app
if /i "%~1"=="phone" goto mobile_app
if /i "%~1"=="mobile" goto mobile_app
if /i "%~1"=="6" goto client_mode
if /i "%~1"=="client" goto client_mode

echo ============================================================================
echo   HELIOS — AUTONOMOUS AI & CODING ECOSYSTEM
echo   Main System: HELIOS (Swarm, Model Router, Tools, Knowledge Memory)
echo   Companion  : Airi (3D VRM Visual Avatar — Launched On-Demand)
echo ============================================================================
echo.
echo   [1] HELIOS Core Server   (Main AI Router :8000, Swarm, RAG, Hardware Arbitrator)
echo   [2] Hikari Coding CLI    (hikari.bat — Interactive Claude Code / Codex Terminal)
echo   [3] HELIOS + Airi        (Core Server :8000 + Airi 3D Companion :8080)
echo   [4] Airi Companion Only  (Standalone 3D VRM Character without :8000)
echo   [5] Mobile Phone App     (start_phone.bat — Expo Go Android / iOS :8081)
echo   [6] HELIOS Client Mode   (start_helios_client.bat — Connect to Server / AI PC)
echo ============================================================================
set /p "CHOICE=Select launch mode [1-6, default=1]: "

if "%CHOICE%"=="2" goto hikari_cli
if "%CHOICE%"=="3" goto full_spec
if "%CHOICE%"=="4" goto char_only
if "%CHOICE%"=="5" goto mobile_app
if "%CHOICE%"=="6" goto client_mode

:core_only
echo [*] Starting HELIOS Core AI Router (:8000)...
cd /d "%~dp0ai-router"
call start.bat
goto :eof

:hikari_cli
echo [*] Launching Hikari Autonomous Coding CLI...
call "%~dp0hikari.bat"
goto :eof

:full_spec
echo [*] Launching HELIOS Core with Airi Companion...
call "%~dp0start_helios_full_spec.bat"
goto :eof

:char_only
echo [*] Launching Airi Companion Standalone...
call "%~dp0start_airi.bat"
goto :eof

:mobile_app
echo [*] Launching Mobile Phone Companion (Expo Go :8081)...
call "%~dp0start_phone.bat"
goto :eof

:client_mode
echo [*] Launching HELIOS Client Suite...
call "%~dp0start_helios_client.bat"
goto :eof

