$scriptDir = $PSScriptRoot
$venvPath = Join-Path $scriptDir "../../.venv/Scripts/Activate.ps1"

if (Test-Path $venvPath) {
    . $venvPath
    Push-Location (Join-Path $scriptDir "../../src")
    uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --timeout-keep-alive 5
    Pop-Location
}
else {
    Write-Error "Virtual environment not found. Run: python -m venv .venv from project root"
}
