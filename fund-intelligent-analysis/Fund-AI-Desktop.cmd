@echo off
chcp 65001 >nul
title Fund AI Desktop
cd /d "%~dp0"

if not exist "scripts\desktop.ps1" (
    echo [ERROR] scripts\desktop.ps1 was not found.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desktop.ps1"
