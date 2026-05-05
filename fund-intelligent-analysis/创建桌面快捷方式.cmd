@echo off
chcp 65001 >nul
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root=(Get-Location).Path; $ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Fund AI.lnk'); $lnk.TargetPath=Join-Path $root 'Fund-AI-Desktop.vbs'; $lnk.WorkingDirectory=$root; $lnk.IconLocation=(Join-Path $root 'assets\fund-ai.ico'); $lnk.Description='Fund AI Desktop'; $lnk.Save(); Write-Host '已创建桌面快捷方式：Fund AI'"

pause
