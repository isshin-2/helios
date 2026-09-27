# start_background.ps1
Write-Host "Starting HELIOS and dependencies in the background..."

# Start Ollama (Hidden)
Write-Host "Starting Ollama..."
Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue

# Ensure Virtual Environment is set up
if (-Not (Test-Path "venv\Scripts\activate.ps1")) {
    Write-Host "Virtual environment not found. Please run start.bat first to set it up."
    exit
}

# Start HELIOS Backend (Hidden)
Write-Host "Starting HELIOS Backend..."
Start-Process ".\venv\Scripts\python.exe" -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000" -WindowStyle Hidden

Write-Host "Apps started in the background!"
Write-Host "Visit http://localhost:8000 in your browser."
Write-Host "To stop them later, you can run: taskkill /F /IM uvicorn.exe (or python.exe) and taskkill /F /IM ollama.exe"
