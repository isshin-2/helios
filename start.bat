@echo off
echo Starting HELIOS setup...

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in your PATH. Please install Python 3.9+.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist "venv\Scripts\activate" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate

:: Install requirements
echo Installing requirements...
pip install -r requirements.txt

:: Initialize database
echo Initializing SQLite Database...
python -c "import db; db.init_db()"

:: Start Uvicorn Server
echo Starting HELIOS Server...
echo Visit http://localhost:8000 in your browser.
python -m uvicorn main:app --host 0.0.0.0 --port 8000
