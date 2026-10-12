@echo off
setlocal
cd /d "%~dp0"

set "PY_EXE=ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

"%PY_EXE%" helios_cmd.py %*
