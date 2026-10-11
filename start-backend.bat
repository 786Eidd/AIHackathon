@echo off
rem Starts the NexGen backend on http://localhost:8000
rem   start-backend.bat        this PC only (default)
rem   start-backend.bat lan    also reachable from phones/PCs on your network
rem                            (the API has no login - only use on a trusted network)
cd /d "%~dp0next-gen-backend"

if not exist .venv\Scripts\python.exe (
    echo [setup] Creating virtual environment and installing dependencies...
    python -m venv .venv || exit /b 1
    .venv\Scripts\python.exe -m pip install -r requirements.txt || exit /b 1
)

set HOST=127.0.0.1
if /i "%1"=="lan" set HOST=0.0.0.0

.venv\Scripts\python.exe -m uvicorn app.main:app --host %HOST% --port 8000 --workers 1
