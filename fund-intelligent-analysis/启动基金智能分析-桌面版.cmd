@echo off
chcp 65001 >nul
title 基金智能分析 桌面版
cd /d "%~dp0"

if not exist "scripts\desktop.ps1" (
    echo [错误] 未找到 scripts\desktop.ps1，请确认本文件在项目根目录中。
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desktop.ps1"
