@echo off
setlocal EnableDelayedExpansion

:: Change directory to the parent directory (project root) where the script is located
cd /d "%~dp0.."

:menu
cls
echo ==================================================
echo         HELIOS TEST ^& DEMO MENU
echo ==================================================
echo.
echo === VISUAL DEMOS (Popups ^& Overlays) ===
echo   [1] Visual Demo: SoM Grid Overlay
echo   [2] Visual Demo: Desktop WebView Overlay
echo   [3] Visual Demo: Autonomous Warning Banner
echo   [4] Visual Demo: AI Core Desktop Overlay (PyQt5)
echo   [5] HELIOS Full Desktop App (Site UI Match)
echo.
echo === UNIT TESTS ===
echo   [6] Run ALL Overlay Unit Tests
echo   [7] Run ALL Project Unit Tests (tests folder)
echo.
echo   [0] Exit
echo.
set /p choice="Enter your choice (0-7): "

set "PYTHONPATH=."

if "%choice%"=="1" (
    echo.
    echo Running Visual Demo: SoM Grid Overlay...
    .\venv\Scripts\python.exe tests\overlays\demo_som_overlay.py
    echo.
    pause
    goto menu
)
if "%choice%"=="2" (
    echo.
    echo Running Visual Demo: Desktop WebView Overlay...
    .\venv\Scripts\python.exe tests\overlays\demo_ui_overlay.py
    echo.
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    echo Running Visual Demo: Autonomous Warning Banner...
    .\venv\Scripts\python.exe tests\overlays\demo_autonomous_overlay.py
    echo.
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    echo Running Visual Demo: AI Core Desktop Overlay...
    .\venv\Scripts\python.exe helios_desktop.py
    echo.
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    echo Running HELIOS Full Desktop App...
    .\venv\Scripts\python.exe desktop_app.py
    echo.
    pause
    goto menu
)
if "%choice%"=="6" (
    echo.
    echo Running ALL Overlay Unit Tests...
    .\venv\Scripts\python.exe -m unittest discover tests/overlays
    echo.
    pause
    goto menu
)
if "%choice%"=="7" (
    echo.
    echo Running ALL Project Unit Tests...
    .\venv\Scripts\python.exe -m unittest discover tests
    echo.
    pause
    goto menu
)
if "%choice%"=="0" (
    exit /b
)

echo.
echo Invalid choice. Please try again.
pause
goto menu
