@echo off
title HELIOS User Edition — Solstice Avatar Companion (:8082 ^& :8080)
setlocal
cd /d "%~dp0"

echo ==============================================================================
echo   HELIOS USER EDITION (SOLSTICE AVATAR COMPANION)
echo   - Solstice Engine   : http://localhost:8082
echo   - 3D Avatar WebGL   : http://localhost:8080
echo   - Biometrics Gate   : Local Speaker Verification Active
echo ==============================================================================

set "PY_EXE=ai-router\venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

:: Check Budget Hardware Warning
"%PY_EXE%" -c "import sys; sys.path.insert(0, 'ai-router'); from core.hardware_governor import HardwareGovernor; print(HardwareGovernor().get_advisory_banner())"

:: Start Solstice Telemetry Engine in background
start "Solstice Avatar Engine [Port 8082]" cmd /c "%PY_EXE% engines\solstice\server.py"

:: Launch 3D Experience (Boots 3D server on 8080 and opens browser)
"%PY_EXE%" scripts\launch_3d_experience.py
