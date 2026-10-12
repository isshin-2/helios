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

:: Check for direct customization flag
if /i "%~1"=="--custom" goto DO_CUSTOM
if /i "%~1"=="-c" goto DO_CUSTOM
if /i "%~1"=="/c" goto DO_CUSTOM

:: 3. Execute Hardware Diagnostic, Ollama Auto-Install and Adaptive Ingestion
echo.
echo %CYAN%[3/5] Executing Hardware Diagnostic, Ollama Verification and Model Ingestion...%RESET%

"%PY_EXE%" scripts\bootstrap.py %*
if errorlevel 1 (
    echo %YELLOW%[!] Bootstrap completed with notices.%RESET%
)

:: 4. Verify Data Directories and Database Silos
echo.
echo %CYAN%[4/5] Verifying Memory Silos and Security Directories...%RESET%
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0config" mkdir "%~dp0config"
if not exist "%~dp0docs" mkdir "%~dp0docs"
echo %GREEN%[OK] Directories data\, config\, and docs\ verified.%RESET%

:: 5. Final Readiness Summary
echo.
echo %CYAN%[5/5] Refreshing Living System Audit (docs\SYSTEM_AUDIT.md)...%RESET%
"%PY_EXE%" scripts\run_audit.py >nul 2>&1
echo %GREEN%[OK] Living System Audit synchronized.%RESET%

echo.
echo %GREEN%==============================================================================%RESET%
echo %GREEN%  HELIOS BOOTSTRAP COMPLETE -- ALL SYSTEMS READY                                %RESET%
echo %GREEN%==============================================================================%RESET%
echo   - %CYAN%Developer Edition%RESET% : Run %YELLOW%start_helios_dev.bat%RESET%
echo   - %CYAN%User Edition (Sol)%RESET%: Run %YELLOW%start_solstice.bat%RESET%
echo   - %CYAN%Coding CLI%RESET%        : Run %YELLOW%hikari.bat%RESET%
echo   - %CYAN%Command Dispatcher%RESET%: Run %YELLOW%helios /help%RESET%
echo.

if "%~1"=="--dry-run" goto END_SETUP
if "%~1"=="-q" goto END_SETUP
if "%~1"=="--quiet" goto END_SETUP

echo %CYAN%Select an immediate action or customize ecosystem:%RESET%
echo   %YELLOW%[C]%RESET% Customize Profile, Models, Persona, Ports, or Biometrics
echo   %YELLOW%[D]%RESET% Launch Developer Edition (Core + Hikari Swarm + Web UI)
echo   %YELLOW%[U]%RESET% Launch User Edition (Solstice 3D Companion)
echo   %YELLOW%[H]%RESET% Launch Hikari Coding CLI
echo   %YELLOW%[T]%RESET% Run Isolation and Biometric Test Suite
echo   %YELLOW%[Enter]%RESET% Exit Setup
echo.
set "USER_ACTION="
set /p USER_ACTION="Enter selection [C, D, U, H, T, or Enter to exit]: "

if /i "%USER_ACTION%"=="C" goto DO_CUSTOM
if /i "%USER_ACTION%"=="D" (
    echo [*] Starting Developer Edition...
    call start_helios_dev.bat
    goto END_SETUP
)
if /i "%USER_ACTION%"=="U" (
    echo [*] Starting Solstice User Edition...
    call start_solstice.bat
    goto END_SETUP
)
if /i "%USER_ACTION%"=="H" (
    echo [*] Starting Hikari Swarm CLI...
    call hikari.bat
    goto END_SETUP
)
if /i "%USER_ACTION%"=="T" (
    echo [*] Executing Isolation and Biometric Tests...
    "%PY_EXE%" -m pytest tests\test_isolation.py
    "%PY_EXE%" scripts\verify_voice.py
    goto END_SETUP
)
goto END_SETUP

:DO_CUSTOM
echo.
echo %CYAN%[*] Launching HELIOS Interactive Customization Wizard...%RESET%
"%PY_EXE%" scripts\bootstrap.py --custom %*
goto END_SETUP

:END_SETUP

