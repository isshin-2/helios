@echo off
title HELIOS Mobile Companion Addon (Expo)
cd /d "%~dp0"

echo ==============================================================================
echo   HELIOS MOBILE ADDON (EXPO / REACT NATIVE)
echo   - Directory : C:\projects\mobile-addon
echo   - Target    : Android / iOS / Web
echo ==============================================================================

where npx >nul 2>&1
if errorlevel 1 (
    echo [X] Node.js / npx is required to run Expo.
    pause
    exit /b 1
)

call npx expo start
