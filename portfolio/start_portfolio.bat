@echo off
title Krithik Mahesh - Engineering Portfolio (HELIOS)
cd /d "%~dp0"

echo ======================================================================
echo   KRITHIK MAHESH (@isshin-2) -- EMBEDDED & FULL-STACK IOT PORTFOLIO
echo ======================================================================
echo.
echo [1/3] Checking environment...
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH!
    pause
    exit /b 1
)

echo [2/3] Checking dependencies...
if not exist "node_modules" (
    echo Installing node dependencies...
    call npm install
)

echo [3/3] Launching Portfolio on http://localhost:5174...
start "" http://localhost:5174

call npm run dev
