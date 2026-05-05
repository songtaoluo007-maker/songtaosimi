@echo off
chcp 65001 >nul
title Stop Fund AI
echo Stopping Fund AI services...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = @(8000,3000); foreach ($p in $ports) { $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue; foreach ($c in $conns) { if ($c.OwningProcess -gt 0) { try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop; Write-Host ('Stopped process on port ' + $p + ': ' + $c.OwningProcess) } catch { Write-Host ('Failed to stop process on port ' + $p + ': ' + $_.Exception.Message) } } } }"

echo.
echo Done.
pause
