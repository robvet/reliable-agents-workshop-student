auth@echo off
echo Starting Model Fusion Playground Backend and Frontend...
echo.

start "Backend" cmd /k "cd /d %~dp0..\..\src && ..\..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul

start "Frontend" cmd /k "cd /d %~dp0..\..\src && ..\..\.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py"

echo Both services started!
pause
