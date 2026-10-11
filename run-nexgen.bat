@echo off
rem One-click start: launches the NexGen backend in its own window (if it is
rem not already running), waits until it answers, then opens the dashboard.
title NexGen launcher

curl -s -m 2 -o nul http://127.0.0.1:8000/api/v1/health
if not errorlevel 1 goto open

echo Starting NexGen... this takes about 20 seconds.
start "NexGen backend - keep this window open" /min cmd /k "%~dp0start-backend.bat"

set /a tries=0
:wait
timeout /t 2 /nobreak >nul
set /a tries+=1
curl -s -m 2 -o nul http://127.0.0.1:8000/api/v1/health
if not errorlevel 1 goto open
if %tries% lss 60 goto wait

echo.
echo NexGen did not start. Open the minimised "NexGen backend" window to see why.
pause
exit /b 1

:open
start "" http://localhost:8000/login
