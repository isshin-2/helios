@echo off
title HELIOS Main Server
setlocal
cd /d "%~dp0"

set "PY_EXE=%~dp0ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

:: If run with no arguments, or with 'main' / 'core' / 'server', launch HELIOS Main Server directly
if "%~1"=="" goto run_main
if /i "%~1"=="main" goto run_main
if /i "%~1"=="/main" goto run_main
if /i "%~1"=="core" goto run_main
if /i "%~1"=="/core" goto run_main
if /i "%~1"=="server" goto run_main
if /i "%~1"=="/server" goto run_main

:: Otherwise dispatch command via helios_cmd.py
"%PY_EXE%" helios_cmd.py %*
goto :eof

:run_main
echo ==============================================================================
echo   HELIOS — Starting Main AI Router (:8000)...
echo ==============================================================================
cd /d "%~dp0ai-router"
if exist "start.bat" (
    call start.bat
) else (
    "%PY_EXE%" main.py
)
