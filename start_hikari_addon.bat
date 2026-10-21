@echo off
title Hikari Addon - Autonomous Coding Swarm Engine (:8001)
setlocal
cd /d "%~dp0"

echo ==============================================================================
echo   HIKARI ADDON - AUTONOMOUS CODING SWARM ENGINE (PORT 8001)
echo   Standalone Addon for HELIOS Ecosystem
echo ==============================================================================

set "HELIOS_DIR=%~dp0..\HELIOS"
set "PY_EXE=%HELIOS_DIR%\ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

"%PY_EXE%" server.py
