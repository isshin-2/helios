@echo off
title HELIOS — AI PC Node Setup
echo ============================================================================
echo   HELIOS — DEDICATED AI PC WORKSTATION SETUP
echo   Target: RTX 5060 Ti (16 GB VRAM) + 64 GB DDR5 RAM
echo ============================================================================
echo.

cd /d "%~dp0..\ai-router"

:: 1. Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [-] Python is not installed or not in PATH! Please install Python 3.10-3.13.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
if not exist "venv\Scripts\python.exe" (
    echo [*] Creating virtual environment...
    python -m venv venv
)

:: 3. Install Core Dependencies
echo [*] Installing requirements...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

:: 4. Verify Local Ollama on AI PC
echo [*] Verifying Ollama cluster models...
venv\Scripts\python.exe scripts\pull_models_ai_pc.py --check

:: 5. Create AI PC .env if needed
if not exist ".env" (
    echo [*] Generating optimized AI PC .env configuration...
    (
        echo DEPLOYMENT_MODE=local
        echo LLM_PROVIDER=ollama
        echo OLLAMA_HOST=http://127.0.0.1:11434
        echo PAIR_HOST=http://127.0.0.1:11434
        echo BOT_NAME=HELIOS
        echo WAKE_WORD=helios
        echo PERSONALITY=helpful, professional, and concise
        echo VOICE_ENABLED=true
        echo VOICE_BACKEND=kokoro
        echo VOICE_NAME=af_heart
        echo VOICE_SPEED=1.0
        echo ENABLE_DESKTOP_APP=false
        echo ENABLE_HOT_MIC=false
    ) > .env
)

echo.
echo ============================================================================
echo   [+] AI PC SETUP COMPLETE!
echo   Run 'start_ai_pc.bat' to launch the full HELIOS server on this machine.
echo ============================================================================
pause
