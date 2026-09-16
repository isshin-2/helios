@echo off
setlocal EnableDelayedExpansion
title HELIOS Server

:: Enable ANSI colors for Windows 10+
for /F "delims=#" %%E in ('"prompt #$E# & for %%a in (1) do rem"') do set "ESC=%%E"
set "CYAN=%ESC%[1;36m"
set "WHITE=%ESC%[1;37m"
set "GREEN=%ESC%[1;32m"
set "RED=%ESC%[1;31m"
set "RESET=%ESC%[0m"

echo %CYAN%Starting HELIOS...%RESET%

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[X] Python is not installed or not in your PATH. Please install Python 3.10+.%RESET%
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist "venv\Scripts\activate.bat" (
    echo %WHITE%[*] Creating virtual environment...%RESET%
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install requirements
echo %WHITE%[*] Verifying requirements...%RESET%
pip install -q -r requirements.txt

:: Run Interactive Setup (Runs once if .setup_complete missing)
python setup.py

:: Start Uvicorn Server
echo.
echo %GREEN%=======================================================%RESET%
echo %CYAN%   HELIOS Server Starting...%RESET%
echo %WHITE%   Local UI: http://localhost:8000%RESET%
echo %GREEN%=======================================================%RESET%
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000
