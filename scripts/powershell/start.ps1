# Start both backend and frontend servers
# Can be run from any directory

$scriptDir = $PSScriptRoot
$venvPath = Join-Path $scriptDir "../../.venv/Scripts/Activate.ps1"

if (Test-Path $venvPath) {
    # Activate virtual environment
    . $venvPath
    
    $srcDir = Join-Path $scriptDir "../../src"
    # Start backend in new window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$srcDir'; . '$venvPath'; uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --timeout-keep-alive 5"
    
    # Start frontend in new window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$srcDir'; . '$venvPath'; python -m streamlit run ui/streamlit_app.py"
    
    Write-Host "Started backend (port 8000) and frontend (port 8501) in separate windows" -ForegroundColor Green
}
else {
    Write-Error "Virtual environment not found at $venvPath"
    Write-Error "Run from project root: python -m venv .venv"
}
