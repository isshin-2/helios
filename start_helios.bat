@echo off
title HELIOS Main Server (:8000)
setlocal
cd /d "%~dp0"

echo ==============================================================================
echo   HELIOS — Starting Main AI Router (:8000)...
echo ==============================================================================
cd /d "%~dp0ai-router"
call start.bat
