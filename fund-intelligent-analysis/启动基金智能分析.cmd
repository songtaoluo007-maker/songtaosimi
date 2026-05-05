@echo off
chcp 65001 >nul
title 基金智能分析
cd /d "%~dp0"

echo ==========================================
echo   Fund AI - Local Launcher
echo ==========================================
echo.

if not exist "scripts\launch.ps1" (
    echo [错误] 未找到 scripts\launch.ps1，请确认本文件在项目根目录中。
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1"
