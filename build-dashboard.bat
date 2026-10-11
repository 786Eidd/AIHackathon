@echo off
rem Builds the dashboard into nextgen-frontend\dist. When that folder exists
rem the backend serves the dashboard itself, so the whole system runs from
rem one process on one port: http://<device-ip>:8000
cd /d "%~dp0nextgen-frontend"

if not exist node_modules (
    call npm install || exit /b 1
)

call npm run build
