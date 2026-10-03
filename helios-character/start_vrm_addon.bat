@echo off
title HELIOS Character Add-On (Port 8080)
echo ============================================================
echo   HELIOS Character Presentation Add-On (VRM / Live2D)
echo   - Character Viewer Server : http://localhost:8080
echo   - HELIOS Core Protocol    : ws://localhost:8000/ws/character
echo ============================================================
cd /d "%~dp0"
"%~dp0..\ai-router\venv\Scripts\python.exe" ai_server.py
pause
