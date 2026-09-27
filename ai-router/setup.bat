@echo off
setlocal EnableDelayedExpansion
title HELIOS - Initial Setup & Configuration

:: Enable ANSI colors for Windows 10+
for /F "delims=#" %%E in ('"prompt #$E# & for %%a in (1) do rem"') do set "ESC=%%E"

:: Define Colors
set "CYAN=%ESC%[1;36m"
set "BLUE=%ESC%[1;34m"
set "WHITE=%ESC%[1;37m"
set "GREEN=%ESC%[1;32m"
set "YELLOW=%ESC%[1;33m"
set "RED=%ESC%[1;31m"
set "RESET=%ESC%[0m"

cls
echo %CYAN%
echo    __  __  ______  _       _____   ____    _____ 
echo   ^|  ^|/  ^|^|  ____^|^| ^|     ^|_   _^| / __ \  / ____^|
echo   ^|      ^|^| ^|__   ^| ^|       ^| ^|  ^| ^|  ^| ^|^| (___  
echo   ^|  __  ^|^|  __^|  ^| ^|       ^| ^|  ^| ^|  ^| ^| \___ \ 
echo   ^| ^|  ^| ^|^| ^|____ ^| ^|____  _^| ^|_ ^| ^|__^| ^| ____) ^|
echo   ^|_^|  ^|_^|^|______^|^|______^|^|_____^| \____/ ^|_____/ 
echo.
echo %BLUE%          Artificial Intelligence Router%RESET%
echo.
echo %WHITE%=======================================================%RESET%
echo %CYAN%              HELIOS Setup Utility%RESET%
echo %WHITE%=======================================================%RESET%
echo.

:: 1. System Checks
echo %CYAN%[1/4] Checking System Requirements...%RESET%

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[X] Python is not installed or not in PATH.%RESET%
    echo Please install Python 3.10+ from python.org and try again.
    pause
    exit /b 1
) else (
    for /f "tokens=2" %%I in ('python --version 2^>^&1') do set "PY_VER=%%I"
    echo %GREEN%[V] Python installed: !PY_VER!%RESET%
)

docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN%[V] Docker detected. You can run HELIOS in an isolated container!%RESET%
) else (
    echo %YELLOW%[!] Docker not found. HELIOS will run locally.%RESET%
)

echo.
:: 2. Virtual Environment Setup
echo %CYAN%[2/4] Initializing Virtual Environment...%RESET%

if not exist "venv\Scripts\activate.bat" (
    echo %YELLOW%[*] Creating new Python virtual environment in .\venv ...%RESET%
    python -m venv venv
    if !errorlevel! neq 0 (
        echo %RED%[X] Failed to create virtual environment.%RESET%
        pause
        exit /b 1
    )
    echo %GREEN%[+] Virtual environment created successfully.%RESET%
) else (
    echo %GREEN%[V] Virtual environment already exists.%RESET%
)

echo %YELLOW%[*] Activating environment...%RESET%
call venv\Scripts\activate.bat

echo.
:: 3. Dependencies
echo %CYAN%[3/4] Installing / Verifying Dependencies...%RESET%
echo %WHITE%This might take a moment depending on your internet connection.%RESET%
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo %RED%[X] Failed to install dependencies. Check your requirements.txt.%RESET%
    pause
    exit /b 1
)
echo %GREEN%[+] All dependencies installed!%RESET%

echo.
:: 4. Interactive Configuration
echo %CYAN%[4/4] Launching HELIOS Interactive Configuration...%RESET%
echo.
echo %YELLOW%[TIP]%RESET% For Gmail and Google Drive integration, you will need
echo an OAuth Client ID and Secret from the Google Cloud Console.
echo.
timeout /t 2 /nobreak > nul

:: Run setup python script
python setup.py --reset

if %errorlevel% neq 0 (
    echo %RED%[X] Configuration was aborted or failed.%RESET%
    pause
    exit /b 1
)

echo.
echo %WHITE%=======================================================%RESET%
echo %GREEN%              Configuration Complete!%RESET%
echo %WHITE%=======================================================%RESET%
echo.
echo %CYAN%You can start HELIOS at any time by running:%RESET% %YELLOW%start.bat%RESET%
echo %CYAN%Or run securely in Docker via:%RESET% %YELLOW%docker compose up -d%RESET%
echo.

set /p START_NOW="%WHITE%Would you like to start HELIOS now? [y/N]: %RESET%"
if /i "!START_NOW!"=="y" (
    echo.
    echo %GREEN%Launching HELIOS...%RESET%
    call start.bat
) else (
    echo.
    echo %CYAN%Setup finished. Press any key to exit.%RESET%
    pause > nul
)
