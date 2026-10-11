@echo off
rem Starts the NexGen dashboard on http://localhost:5173
cd /d "%~dp0nextgen-frontend"

if not exist node_modules (
    echo [setup] Installing dependencies...
    call npm install || exit /b 1
)

call npm run dev
