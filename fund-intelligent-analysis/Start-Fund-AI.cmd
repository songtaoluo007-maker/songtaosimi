@echo off
chcp 65001 >nul
title Fund AI
cd /d "%~dp0"

echo ==========================================
echo   Fund AI - Local Launcher
echo ==========================================
echo.

if not exist "scripts\launch.ps1" (
    echo [ERROR] scripts\launch.ps1 was not found.
    echo Please put this file in the project root folder.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1"
