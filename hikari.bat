@echo off
setlocal
:: Verify AI PC is reachable; if offline, run wake script
powershell -NoProfile -Command "if (-not (Test-NetConnection -ComputerName 192.168.100.254 -Port 3389 -InformationLevel Quiet -WarningAction SilentlyContinue)) { Write-Host '[HELIOS] AI PC is offline. Launching AI-PC.ps1 wake script...' -ForegroundColor Yellow; Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"C:\Users\krithik\Desktop\AI-PC.ps1\"' }"

cd /d "%~dp0ai-router"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe helios_code.py %*
) else (
    python helios_code.py %*
)
