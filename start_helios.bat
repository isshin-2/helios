@echo off
title HELIOS Ecosystem Launcher
if /i "%~1"=="1" goto full_spec
if /i "%~1"=="full" goto full_spec
if /i "%~1"=="full_spec" goto full_spec
if /i "%~1"=="2" goto char_only
if /i "%~1"=="character" goto char_only
if /i "%~1"=="character_only" goto char_only

echo ============================================================================
echo   HELIOS — SELECT VERSION TO LAUNCH
echo ============================================================================
echo   [1] Full Spec Version     (ai-router :8000 + Tools + Sandbox + Desktop + Character :8080)
echo   [2] Just the Character    (Standalone 3D VRM Character :8080 + Local Chat + TTS only)
echo ============================================================================
set /p "CHOICE=Select version [1 or 2, default=1]: "
if "%CHOICE%"=="2" goto char_only

:full_spec
call "%~dp0start_helios_full_spec.bat"
goto :eof

:char_only
call "%~dp0start_character_only.bat"
goto :eof
