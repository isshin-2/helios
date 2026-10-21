@echo off
setlocal enabledelayedexpansion
title HELIOS Mobile Phone Companion — Expo Go (Port 8081)
echo ============================================================================
echo   HELIOS MOBILE PHONE COMPANION -- Expo Go / React Native
echo   Bare HELIOS AI Core HUD + Airi 3D VRM Companion + Hikari Terminal
echo ============================================================================
echo.
:: Path resolution for Mobile Addon
set "MOBILE_DIR=%~dp0..\..\..\mobile-addon"
if not exist "%MOBILE_DIR%" set "MOBILE_DIR=%~dp0..\..\mobile_v2"
if not exist "%MOBILE_DIR%" (
    echo [X] Mobile addon not found at C:\projects\mobile-addon.
    pause
    exit /b 1
)
cd /d "%MOBILE_DIR%"

:: Add Android SDK platform-tools (adb) to PATH if present
if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "PATH=%LOCALAPPDATA%\Android\Sdk\platform-tools;%PATH%"
)

:: Check for connected ADB devices
set "HAS_ADB=0"
where adb >nul 2>nul
if %ERRORLEVEL% equ 0 (
    for /f "skip=1 tokens=1,2" %%A in ('adb devices 2^>nul') do (
        if "%%B"=="device" (
            set "HAS_ADB=1"
            set "ADB_DEVICE_ID=%%A"
        )
    )
)

if "!HAS_ADB!"=="1" (
    echo [+] Connected Android device detected via USB: !ADB_DEVICE_ID!
    echo [*] Setting up ADB reverse port forwarding: 8081 Metro, 8000 Core, 8080 Airi, 8085 Live2D
    adb reverse tcp:8081 tcp:8081 >nul 2>nul
    adb reverse tcp:8000 tcp:8000 >nul 2>nul
    adb reverse tcp:8080 tcp:8080 >nul 2>nul
    adb reverse tcp:8085 tcp:8085 >nul 2>nul
    echo [+] ADB ports successfully reversed.
    set "DEFAULT_MODE=1"
) else (
    echo [*] No USB ADB device detected. Defaulting to Wi-Fi / LAN Mode.
    set "DEFAULT_MODE=2"
)
echo.

if not exist node_modules (
    echo [!] Installing mobile dependencies...
    call npm install
)

:: Handle direct argument if provided
if /i "%~1"=="lan" goto launch_lan
if /i "%~1"=="2" goto launch_lan
if /i "%~1"=="usb" goto launch_usb
if /i "%~1"=="adb" goto launch_usb
if /i "%~1"=="1" goto launch_usb
if /i "%~1"=="tunnel" goto launch_tunnel
if /i "%~1"=="3" goto launch_tunnel
if /i "%~1"=="web" goto launch_web
if /i "%~1"=="4" goto launch_web

echo Select connection mode:
if "!HAS_ADB!"=="1" (
    echo   [1] USB Direct Mode   -- Connected phone via USB + ADB reverse :8081 [Auto-Detected]
    echo   [2] LAN Mode          -- Wi-Fi / local IP QR code scan in Expo Go
) else (
    echo   [1] USB Direct Mode   -- Requires USB debugging cable + ADB connection
    echo   [2] LAN Mode          -- Wi-Fi / local IP QR code scan in Expo Go [Recommended]
)
echo   [3] Tunnel Mode       -- Over cellular / remote network via ngrok
echo   [4] Web Mode          -- Local browser emulation
echo ============================================================================
set "MODE_CHOICE=!DEFAULT_MODE!"
set /p "MODE_CHOICE=Select [1-4, default: !DEFAULT_MODE!]: "

if "!MODE_CHOICE!"=="1" goto launch_usb
if "!MODE_CHOICE!"=="2" goto launch_lan
if "!MODE_CHOICE!"=="3" goto launch_tunnel
if "!MODE_CHOICE!"=="4" goto launch_web

if "!DEFAULT_MODE!"=="1" goto launch_usb
goto launch_lan

:launch_usb
echo [*] Starting Expo in ADB / USB mode for Expo Go...
if "!HAS_ADB!"=="1" (
    call npx expo start --localhost -g -a
) else (
    call npx expo start --localhost -g
)
goto finish

:launch_lan
echo [*] Starting Expo in LAN Mode: Scan QR Code with Expo Go on your phone...
call npx expo start --lan -g
goto finish

:launch_tunnel
echo [*] Starting Expo in Tunnel mode...
call npx expo start --tunnel
goto finish

:launch_web
echo [*] Starting Expo in Web browser mode...
call npx expo start --web
goto finish

:finish
pause
