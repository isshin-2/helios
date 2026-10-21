@echo off
setlocal EnableDelayedExpansion
title HELIOS - Unified Setup ^& Configuration

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
echo %BLUE%          Artificial Intelligence Router ^& Autonomous Swarm%RESET%

echo.
echo %WHITE%=======================================================%RESET%
echo %CYAN%              HELIOS Setup Utility%RESET%
echo %WHITE%=======================================================%RESET%
echo.

:: 1. System Requirements Check
echo %CYAN%[1/5] Checking System Requirements...%RESET%

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[X] Python is not installed or not in PATH.%RESET%
    echo Please install Python 3.10-3.13 from python.org and try again.
    pause
    exit /b 1
) else (
    for /f "tokens=2" %%I in ('python --version 2^>^&1') do set "PY_VER=%%I"
    echo %GREEN%[V] Python installed: !PY_VER!%RESET%
)

:: 2. Virtual Environment Setup
echo.
echo %CYAN%[2/5] Initializing Virtual Environment...%RESET%

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

:: Direct CLI routing for voice configuration
if "%~1"=="--voice" goto mode_voice
if "%~1"=="voice" goto mode_voice
if "%~1"=="-v" goto mode_voice

:: 3. Dependencies
echo.
echo %CYAN%[3/5] Installing / Verifying Dependencies...%RESET%
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo %RED%[X] Failed to install dependencies. Check your requirements.txt.%RESET%
    pause
    exit /b 1
)
echo %GREEN%[+] Core dependencies verified!%RESET%

:: 4. Hardware & Network Node Inspection
echo.
set "CFG_BOT_NAME=HELIOS"
set "CFG_USER_NAME=User"
set "CFG_WAKE_WORD=helios"
set "CFG_AI_PC_IP=192.168.100.254"
set "CFG_AI_PC_MAC=30:56:0F:A8:76:05"
set "CFG_AI_PC_BROADCAST=192.168.100.255"
set "CFG_AI_PC_WAKE_SCRIPT="
set "CFG_OLLAMA_HOST=http://127.0.0.1:11434"
set "CFG_SERVER_PORT=8000"
set "CFG_CHARACTER_PORT=8080"
set "CFG_VOICE_NAME=af_heart"
set "CFG_VOICE_BACKEND=kokoro"

if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        if /i "%%A"=="BOT_NAME" set "CFG_BOT_NAME=%%B"
        if /i "%%A"=="USER_NAME" set "CFG_USER_NAME=%%B"
        if /i "%%A"=="WAKE_WORD" set "CFG_WAKE_WORD=%%B"
        if /i "%%A"=="AI_PC_IP" set "CFG_AI_PC_IP=%%B"
        if /i "%%A"=="AI_PC_MAC" set "CFG_AI_PC_MAC=%%B"
        if /i "%%A"=="AI_PC_BROADCAST" set "CFG_AI_PC_BROADCAST=%%B"
        if /i "%%A"=="AI_PC_WAKE_SCRIPT" set "CFG_AI_PC_WAKE_SCRIPT=%%B"
        if /i "%%A"=="OLLAMA_HOST" set "CFG_OLLAMA_HOST=%%B"
        if /i "%%A"=="SERVER_PORT" set "CFG_SERVER_PORT=%%B"
        if /i "%%A"=="CHARACTER_PORT" set "CFG_CHARACTER_PORT=%%B"
        if /i "%%A"=="VOICE_NAME" set "CFG_VOICE_NAME=%%B"
        if /i "%%A"=="VOICE_BACKEND" set "CFG_VOICE_BACKEND=%%B"
    )
)

echo %CYAN%[4/5] Probing Local Hardware & Network Nodes...%RESET%
python -c "from core.ai_pc_manager import is_ai_pc_reachable; exit(0 if is_ai_pc_reachable(timeout=0.8) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "AI_PC_ONLINE=1"
    set "DEFAULT_PROFILE=2"
    echo   -^> NVIDIA PAIR Node (!CFG_AI_PC_IP!): %GREEN%ONLINE (Reachable)%RESET%
) else (
    set "AI_PC_ONLINE=0"
    set "DEFAULT_PROFILE=1"
    echo   -^> NVIDIA PAIR Node (!CFG_AI_PC_IP!): %YELLOW%OFFLINE / Standby%RESET% (Recommended: [1] Local)
)

:: 5. Configuration Mode
echo.
echo %CYAN%[5/5] Select Deployment Profile:%RESET%
echo %WHITE%-------------------------------------------------------%RESET%
echo   %GREEN%[1]%RESET% %WHITE%Local Mode%RESET% (Zero network config: Ollama runs 100%% on this machine)
echo   %WHITE%[2]%RESET% %WHITE%NVIDIA PAIR Mode%RESET% (Routes heavy tasks over LAN to NVIDIA GPU workstation)
echo   %WHITE%[3]%RESET% %WHITE%API Mode%RESET% (Cloud-based via external APIs - Gemini, Groq, NVIDIA NIM)
echo   %WHITE%[4]%RESET% %WHITE%Custom Interactive Configuration%RESET% (Full step-by-step setup wizard)
echo   %CYAN%[5]%RESET% %WHITE%Voice Configuration & Cloning%RESET% (Add custom voice / select Kokoro voice)
echo %WHITE%-------------------------------------------------------%RESET%
set "PROFILE_CHOICE="
set /p PROFILE_CHOICE="Select profile [1-5, default=!DEFAULT_PROFILE!]: "
if "!PROFILE_CHOICE!"=="" set "PROFILE_CHOICE=!DEFAULT_PROFILE!"

if "%PROFILE_CHOICE%"=="1" goto mode_local
if "%PROFILE_CHOICE%"=="2" goto mode_pair
if "%PROFILE_CHOICE%"=="3" goto mode_api
if "%PROFILE_CHOICE%"=="4" goto mode_custom
if "%PROFILE_CHOICE%"=="5" goto mode_voice


:mode_pair
echo.
echo %GREEN%[*] Configuring NVIDIA PAIR Mode...%RESET%
echo %YELLOW%(Press ENTER to accept default in brackets)%RESET%
echo.

set /p "INP_AI_PC_IP=  NVIDIA PAIR Workstation IP [!CFG_AI_PC_IP!]: "
if not "!INP_AI_PC_IP!"=="" set "CFG_AI_PC_IP=!INP_AI_PC_IP!"

set /p "INP_AI_PC_MAC=  NVIDIA PAIR MAC Address for WoL [!CFG_AI_PC_MAC!]: "
if not "!INP_AI_PC_MAC!"=="" set "CFG_AI_PC_MAC=!INP_AI_PC_MAC!"

set /p "INP_USER_NAME=  Your Name / Call-Sign [!CFG_USER_NAME!]: "
if not "!INP_USER_NAME!"=="" set "CFG_USER_NAME=!INP_USER_NAME!"

set /p "INP_BOT_NAME=  Assistant Name [!CFG_BOT_NAME!]: "
if not "!INP_BOT_NAME!"=="" set "CFG_BOT_NAME=!INP_BOT_NAME!"

set /p "INP_WAKE_SCRIPT=  Custom Wake Script (optional, blank for native WoL) [!CFG_AI_PC_WAKE_SCRIPT!]: "
if not "!INP_WAKE_SCRIPT!"=="" set "CFG_AI_PC_WAKE_SCRIPT=!INP_WAKE_SCRIPT!"

echo %CYAN%[*] Writing .env configuration...%RESET%
(
    echo DEPLOYMENT_MODE=local
    echo LLM_PROVIDER=pair
    echo OLLAMA_HOST=http://!CFG_AI_PC_IP!:11434
    echo PAIR_HOST=http://!CFG_AI_PC_IP!:11434
    echo AI_PC_IP=!CFG_AI_PC_IP!
    echo AI_PC_MAC=!CFG_AI_PC_MAC!
    echo AI_PC_BROADCAST=!CFG_AI_PC_BROADCAST!
    echo AI_PC_WAKE_SCRIPT=!CFG_AI_PC_WAKE_SCRIPT!
    echo AUTO_WAKE_AI_PC=true
    echo VISION_MODEL=moondream:latest
    echo BOT_NAME=!CFG_BOT_NAME!
    echo USER_NAME=!CFG_USER_NAME!
    echo SERVER_PORT=!CFG_SERVER_PORT!
    echo CHARACTER_PORT=!CFG_CHARACTER_PORT!
    echo WAKE_WORD=!CFG_WAKE_WORD!
    echo PERSONALITY=helpful, professional, and concise
    echo VOICE_ENABLED=true
    echo VOICE_BACKEND=!CFG_VOICE_BACKEND!
    echo VOICE_NAME=!CFG_VOICE_NAME!
    echo VOICE_SPEED=1.0
    echo ENABLE_DESKTOP_APP=false
    echo ENABLE_HOT_MIC=false
) > .env
goto finish_setup

:mode_local
echo.
echo %GREEN%[*] Configuring Local Mode...%RESET%
echo %YELLOW%(Press ENTER to accept default in brackets)%RESET%
echo.

set /p "INP_OLLAMA_HOST=  Local Ollama Host URL [!CFG_OLLAMA_HOST!]: "
if not "!INP_OLLAMA_HOST!"=="" set "CFG_OLLAMA_HOST=!INP_OLLAMA_HOST!"

set /p "INP_USER_NAME=  Your Name / Call-Sign [!CFG_USER_NAME!]: "
if not "!INP_USER_NAME!"=="" set "CFG_USER_NAME=!INP_USER_NAME!"

set /p "INP_BOT_NAME=  Assistant Name [!CFG_BOT_NAME!]: "
if not "!INP_BOT_NAME!"=="" set "CFG_BOT_NAME=!INP_BOT_NAME!"

echo %CYAN%[*] Writing .env configuration...%RESET%
(
    echo DEPLOYMENT_MODE=local
    echo LLM_PROVIDER=ollama
    echo OLLAMA_HOST=!CFG_OLLAMA_HOST!
    echo PAIR_HOST=!CFG_OLLAMA_HOST!
    echo AI_PC_IP=127.0.0.1
    echo BOT_NAME=!CFG_BOT_NAME!
    echo USER_NAME=!CFG_USER_NAME!
    echo SERVER_PORT=!CFG_SERVER_PORT!
    echo CHARACTER_PORT=!CFG_CHARACTER_PORT!
    echo WAKE_WORD=!CFG_WAKE_WORD!
    echo PERSONALITY=helpful, professional, and concise
    echo VOICE_ENABLED=true
    echo VOICE_BACKEND=!CFG_VOICE_BACKEND!
    echo VOICE_NAME=!CFG_VOICE_NAME!
    echo VOICE_SPEED=1.0
    echo ENABLE_DESKTOP_APP=false
    echo ENABLE_HOT_MIC=false
) > .env
goto finish_setup

:mode_api
echo.
echo %GREEN%[*] Configuring API Mode (Cloud APIs)...%RESET%
echo %YELLOW%(Press ENTER to accept default in brackets)%RESET%
echo.

set /p "INP_GEMINI_KEY=  Gemini API Key: "
set /p "INP_GROQ_KEY=  Groq API Key: "
set /p "INP_NVIDIA_KEY=  NVIDIA API Key: "

set /p "INP_USER_NAME=  Your Name / Call-Sign [!CFG_USER_NAME!]: "
if not "!INP_USER_NAME!"=="" set "CFG_USER_NAME=!INP_USER_NAME!"

set /p "INP_BOT_NAME=  Assistant Name [!CFG_BOT_NAME!]: "
if not "!INP_BOT_NAME!"=="" set "CFG_BOT_NAME=!INP_BOT_NAME!"

echo %CYAN%[*] Writing .env configuration...%RESET%
(
    echo DEPLOYMENT_MODE=online
    echo LLM_PROVIDER=gemini
    echo OLLAMA_HOST=http://127.0.0.1:11434
    echo PAIR_HOST=http://127.0.0.1:11434
    echo AI_PC_IP=127.0.0.1
    echo GEMINI_API_KEY=!INP_GEMINI_KEY!
    echo GROQ_API_KEY=!INP_GROQ_KEY!
    echo NVIDIA_API_KEY=!INP_NVIDIA_KEY!
    echo BOT_NAME=!CFG_BOT_NAME!
    echo USER_NAME=!CFG_USER_NAME!
    echo SERVER_PORT=!CFG_SERVER_PORT!
    echo CHARACTER_PORT=!CFG_CHARACTER_PORT!
    echo WAKE_WORD=!CFG_WAKE_WORD!
    echo PERSONALITY=helpful, professional, and concise
    echo VOICE_ENABLED=true
    echo VOICE_BACKEND=!CFG_VOICE_BACKEND!
    echo VOICE_NAME=!CFG_VOICE_NAME!
    echo VOICE_SPEED=1.0
    echo ENABLE_DESKTOP_APP=false
    echo ENABLE_HOT_MIC=false
) > .env
goto finish_setup

:mode_custom
echo.
echo %CYAN%[*] Launching Interactive Configuration Wizard...%RESET%
python setup.py --reset
goto finish_setup

:mode_voice
echo.
echo %CYAN%[*] Launching HELIOS Voice Setup Utility...%RESET%
set "VOICE_CONFIGURED=1"
python scripts\setup_voice.py
goto finish_setup

:finish_setup
if not defined VOICE_CONFIGURED if not "%PROFILE_CHOICE%"=="5" (
    echo.
    set /p CONFIGURE_VOICE="%WHITE%Would you like to configure or add a voice profile now? [y/N]: %RESET%"
    if /i "!CONFIGURE_VOICE!"=="y" (
        python scripts\setup_voice.py
    )
)


echo.
echo %WHITE%=======================================================%RESET%
echo %GREEN%              Setup Completed Successfully!%RESET%
echo %WHITE%=======================================================%RESET%

echo.
echo %CYAN%How to run HELIOS:%RESET%
echo   - %GREEN%Main Core Server%RESET% : Run %YELLOW%start.bat%RESET% (or root %YELLOW%start_helios.bat%RESET%)
echo   - %GREEN%Coding CLI%RESET%       : Run %YELLOW%hikari.bat%RESET% (Claude Code / Codex Terminal)
echo   - %GREEN%Airi Companion%RESET%   : Run %YELLOW%start_airi.bat%RESET% (3D visual avatar for company)
echo.

set /p START_NOW="%WHITE%Would you like to start HELIOS now? [y/N]: %RESET%"
if /i "!START_NOW!"=="y" (
    echo.
    echo %GREEN%Launching HELIOS...%RESET%
    call start.bat
) else (
    echo.
    echo %CYAN%Press any key to exit.%RESET%
    pause > nul
)
