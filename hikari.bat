@echo off
title Hikari — HELIOS Autonomous Coding Swarm (Standalone Addon)
setlocal

cd /d "%~dp0"

:: Discover python executable
set "PY_EXE=%~dp0..\HELIOS\ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=venv\Scripts\python.exe"
)
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

:: Launch Hikari CLI
"%PY_EXE%" helios_code.py %*
