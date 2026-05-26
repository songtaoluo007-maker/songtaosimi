@echo off
set SCRIPT_DIR=%~dp0
set DB_PATH=%SCRIPT_DIR%..\data\fund_quant.db
set BACKUP_DIR=%SCRIPT_DIR%..\data\backups

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set TS=%%I
set TIMESTAMP=%TS:~0,14%
mkdir "%BACKUP_DIR%" 2>nul
copy /Y "%DB_PATH%" "%BACKUP_DIR%\fund_quant_%TIMESTAMP%.db" >nul

if exist "%BACKUP_DIR%\fund_quant_%TIMESTAMP%.db" (
    echo [OK] Backup created: fund_quant_%TIMESTAMP%.db
) else (
    echo [FAIL] Backup failed!
    exit /b 1
)

rem Clean up backups older than 7 days
forfiles /p "%BACKUP_DIR%" /m "fund_quant_*.db" /d -7 /c "cmd /c del @file" 2>nul
echo [OK] Cleaned up old backups (keeping 7 days)
