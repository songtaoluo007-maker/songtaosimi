@echo off
chcp 65001 >nul
title Fund AI Logs
cd /d "%~dp0"

echo ==== launcher.log ====
if exist "data\logs\launcher.log" (
    powershell -NoProfile -Command "Get-Content 'data\logs\launcher.log' -Tail 80"
) else (
    echo launcher.log not found
)

echo.
echo ==== backend_stderr.log ====
if exist "data\logs\backend_stderr.log" (
    powershell -NoProfile -Command "Get-Content 'data\logs\backend_stderr.log' -Tail 80"
) else (
    echo backend_stderr.log not found
)

echo.
pause
