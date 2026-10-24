@echo off
title Solstice Addon - Avatar & Companion Telemetry Engine (:8082)
setlocal
cd /d "%~dp0"

echo ==============================================================================
echo   SOLSTICE ADDON - AVATAR & COMPANION ENGINE (PORT 8082)
echo   Standalone Addon for HELIOS Ecosystem
echo ==============================================================================

set "HELIOS_DIR=%~dp0..\HELIOS"
set "PY_EXE=%HELIOS_DIR%\ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

"%PY_EXE%" server.py
