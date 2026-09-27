@echo off
title HELIOS 3D VRM Companion Add-On (Port 8080)
echo ============================================================
echo   HELIOS 3D VRM Companion Add-On (Riko Architecture)
echo   - Add-On Viewer Server : http://localhost:8080
echo   - HELIOS Core Bridge   : http://localhost:8000 (Auto-Connect)
echo ============================================================
cd /d "%~dp0"
"%~dp0..\ai-router\venv\Scripts\python.exe" ai_server.py
pause
