#!/usr/bin/env bash

# HELIOS Mac Initialization Script
# Double-click this file in Finder to start the server

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "🚀 Starting HELIOS AI Router for Mac"
echo "=========================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed or not in PATH."
    echo "Please install Python 3 via Homebrew (brew install python3) or from python.org."
    read -p "Press Enter to exit..."
    exit 1
fi

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Check if requirements.txt exists and install dependencies
if [ -f "requirements.txt" ]; then
    echo "⚙️ Installing/Updating dependencies..."
    pip install -r requirements.txt --quiet
else
    # Install basic requirements if file is missing
    echo "⚙️ Installing base dependencies..."
    pip install fastapi uvicorn websockets httpx pytest colorama --quiet
fi

echo "=========================================="
echo "🌐 Starting Uvicorn Server..."
echo "=========================================="

# Initialize database
echo "Initializing SQLite Database..."
python -c "import db; db.init_db()"

# Start the server on port 8000
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Keep terminal open if the server stops or crashes
read -p "Server stopped. Press Enter to exit..."
