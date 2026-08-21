#!/bin/bash
echo "Starting HELIOS setup..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "python3 could not be found. Please install Python 3.9+."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Initialize database
echo "Initializing SQLite Database..."
python -c "import db; db.init_db()"

# Start Uvicorn Server
echo "Starting HELIOS Server..."
echo "Visit http://localhost:8000 in your browser."
python -m uvicorn main:app --host 0.0.0.0 --port 8000
