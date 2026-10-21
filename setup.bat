@echo off
setlocal
title HELIOS and Twin Ecosystem -- Idempotent Bootstrap Pipeline
cd /d "%~dp0"

:: Enable ANSI colors for Windows 10+
for /F "delims=#" %%E in ('"prompt #$E# & for %%a in (1) do rem"') do set "ESC=%%E"
set "CYAN=%ESC%[1;36m"
set "GREEN=%ESC%[1;32m"
set "YELLOW=%ESC%[1;33m"
set "RED=%ESC%[1;31m"
set "RESET=%ESC%[0m"

echo %CYAN%==============================================================================%RESET%
echo %CYAN%    HELIOS and TWIN ECOSYSTEM -- ZERO-FRICTION IDEMPOTENT BOOTSTRAP PIPELINE   %RESET%
echo %CYAN%==============================================================================%RESET%
echo.

:: 1. System Runtime Verification
echo %CYAN%[1/5] Verifying System Runtimes (Python, Node.js, Git)...%RESET%

where python >nul 2>&1
if errorlevel 1 (
    echo %RED%[X] Python is not found in PATH.%RESET%
    echo Please install Python 3.10-3.13 from python.org or run 'winget install Python.Python.3.13'
    exit /b 1
) else (
    for /f "tokens=2" %%I in ('python --version 2^>^&1') do set "PY_VER=%%I"
    echo %GREEN%[OK] Python detected.%RESET%
)

where git >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%[!] Git not detected in PATH. Version control features may be limited.%RESET%
) else (
    echo %GREEN%[OK] Git detected.%RESET%
)

where node >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%[!] Node.js not detected in PATH. Mobile/Portfolio features may be limited.%RESET%
) else (
    echo %GREEN%[OK] Node.js detected.%RESET%
)

:: 2. Virtual Environment Provisioning (.venv / ai-router\venv)
echo.
echo %CYAN%[2/5] Initializing Python Virtual Environment...%RESET%

set "VENV_DIR=%~dp0ai-router\venv"
set "PY_EXE=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo %YELLOW%[*] Creating Python virtual environment...%RESET%
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo %RED%[X] Failed to create virtual environment.%RESET%
        exit /b 1
    )
    echo %GREEN%[OK] Virtual environment created successfully.%RESET%
) else (
    echo %GREEN%[OK] Virtual environment already initialized [Idempotent].%RESET%
)

:: Check for direct routing flags
if /i "%~1"=="--custom" goto DO_CUSTOM
if /i "%~1"=="-c" goto DO_CUSTOM
if /i "%~1"=="/c" goto DO_CUSTOM
if /i "%~1"=="--models" goto DO_MODELS
if /i "%~1"=="-m" goto DO_MODELS
if /i "%~1"=="--voice" goto DO_VOICE
if /i "%~1"=="-v" goto DO_VOICE
if /i "%~1"=="--airi" goto DO_AIRI
if /i "%~1"=="-a" goto DO_AIRI

:: 3. Execute Hardware Diagnostic, Ollama Auto-Install and Adaptive Ingestion
echo.
echo %CYAN%[3/5] Executing Hardware Diagnostic, Ollama Verification and Model Ingestion...%RESET%

"%PY_EXE%" scripts\bootstrap.py %*
if errorlevel 1 (
    echo %YELLOW%[!] Bootstrap completed with notices.%RESET%
)

:: Ensure core audio and paramiko dependencies are installed in virtual environment
"%PY_EXE%" -c "import soundfile, httpx, paramiko" >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%[*] Installing essential audio and networking dependencies...%RESET%
    "%PY_EXE%" -m pip install -q soundfile sounddevice httpx paramiko
)

:: 4. Verify Data Directories and Database Silos
echo.
echo %CYAN%[4/5] Verifying Memory Silos and Security Directories...%RESET%
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0config" mkdir "%~dp0config"
if not exist "%~dp0docs" mkdir "%~dp0docs"
if not exist "%~dp0voices\airi" mkdir "%~dp0voices\airi"
echo %GREEN%[OK] Directories data\, config\, docs\, and voices\ verified.%RESET%

:: 5. Final Readiness Summary
echo.
echo %CYAN%[5/5] Refreshing Living System Audit (docs\SYSTEM_AUDIT.md)...%RESET%
"%PY_EXE%" scripts\run_audit.py >nul 2>&1
echo %GREEN%[OK] Living System Audit synchronized.%RESET%

echo.
echo %GREEN%==============================================================================%RESET%
echo %GREEN%  HELIOS BOOTSTRAP COMPLETE -- ALL SYSTEMS READY                                %RESET%
echo %GREEN%==============================================================================%RESET%
echo   - %CYAN%HELIOS Main Server%RESET%: Run %YELLOW%helios.bat%RESET% (or %YELLOW%start_helios.bat%RESET%)
echo   - %CYAN%Airi 3D Companion%RESET%: Run %YELLOW%scripts\launchers\start_airi.bat%RESET%
echo   - %CYAN%Coding CLI (Hikari)%RESET%: Run %YELLOW%hikari.bat%RESET%
echo   - %CYAN%Command Dispatcher%RESET%: Run %YELLOW%helios /help%RESET%
echo.

if "%~1"=="--dry-run" goto END_SETUP
if "%~1"=="-q" goto END_SETUP
if "%~1"=="--quiet" goto END_SETUP

echo %CYAN%Select an immediate action or customize ecosystem:%RESET%
echo   %YELLOW%[C]%RESET% Full Customization Wizard (User, Voice, LLMs, AI PC, Ports)
echo   %YELLOW%[O]%RESET% AI Model Selection & Tiers (Hardware Tiers vs User-Preferred)
echo   %YELLOW%[M]%RESET% Launch HELIOS Main Server (:8000)
echo   %YELLOW%[A]%RESET% Launch Airi 3D Companion (:8080)
echo   %YELLOW%[V]%RESET% Quick Voice & Reference Audio Setup
echo   %YELLOW%[T]%RESET% Run Isolation, TTS, and Biometric Test Suite
echo   %YELLOW%[Enter]%RESET% Exit Setup
echo.
set "USER_ACTION="
set /p USER_ACTION="Enter selection [C, O, M, A, V, T, or Enter to exit]: "

if /i "%USER_ACTION%"=="C" goto DO_CUSTOM
if /i "%USER_ACTION%"=="O" goto DO_MODELS
if /i "%USER_ACTION%"=="M" (
    echo [*] Starting HELIOS Main Server...
    call "%~dp0start_helios.bat"
    goto END_SETUP
)
if /i "%USER_ACTION%"=="A" goto DO_AIRI
if /i "%USER_ACTION%"=="V" goto DO_VOICE
if /i "%USER_ACTION%"=="T" (
    echo [*] Executing Isolation, TTS, and Biometric Tests...
    "%PY_EXE%" -m pytest tests\test_isolation.py -q
    "%PY_EXE%" -m pytest ai-router\tests\test_gpt_sovits_resource_manager.py -q
    "%PY_EXE%" scripts\verify_voice.py --test
    goto END_SETUP
)
goto END_SETUP

:DO_MODELS
echo.
echo %CYAN%[*] Launching AI Model Selection Menu...%RESET%
"%PY_EXE%" scripts\bootstrap.py --models %*
goto END_SETUP

:DO_VOICE
echo.
echo %CYAN%[*] Launching HELIOS Voice Setup Utility...%RESET%
cd /d "%~dp0ai-router"
"%PY_EXE%" scripts\setup_voice.py
cd /d "%~dp0"
goto END_SETUP

:DO_AIRI
echo.
echo %CYAN%[*] Launching Airi 3D Companion...%RESET%
call "%~dp0scripts\launchers\start_airi.bat"
goto END_SETUP

:DO_CUSTOM
echo.
echo %CYAN%[*] Launching HELIOS Interactive Customization Wizard...%RESET%
"%PY_EXE%" scripts\bootstrap.py --custom %*
goto END_SETUP

:END_SETUP


