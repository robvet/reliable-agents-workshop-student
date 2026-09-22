$scriptDir = $PSScriptRoot
$venvPath = Join-Path $scriptDir "../../.venv/Scripts/Activate.ps1"

if (Test-Path $venvPath) {
    . $venvPath
    Push-Location (Join-Path $scriptDir "../../src")
    python -m streamlit run ui/streamlit_app.py
    Pop-Location
}
else {
    Write-Error "Virtual environment not found. Run: python -m venv .venv from project root"
}