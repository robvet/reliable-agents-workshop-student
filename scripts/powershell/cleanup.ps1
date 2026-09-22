# Kill all Python processes and free port 8000
# Run this when things get stuck

Write-Host "Killing all Python processes..." -ForegroundColor Yellow
taskkill /F /IM python.exe 2>$null
taskkill /F /IM pythonw.exe 2>$null

Write-Host "Checking port 8000..." -ForegroundColor Yellow
$portProcess = netstat -ano | findstr :8000
if ($portProcess) {
    Write-Host "Found process on port 8000, killing..." -ForegroundColor Red
    $portProcess | ForEach-Object {
        $processId = ($_ -split '\s+')[-1]
        if ($processId -match '^\d+$') {
            taskkill /F /PID $processId 2>$null
        }
    }
}

Write-Host "Cleanup complete!" -ForegroundColor Green
