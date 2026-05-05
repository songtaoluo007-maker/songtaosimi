param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "data\logs"
$LaunchLog = Join-Path $LogDir "launcher.log"
$Url = "http://127.0.0.1:8000"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

function Write-LaunchLog($Message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $LaunchLog -Value $line -Encoding UTF8
    Write-Host $Message
}

function Find-CommandPath($Names) {
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) {
            return $cmd.Source
        }
    }
    return $null
}

function Find-ExistingPath($Paths) {
    foreach ($path in $Paths) {
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}

$Python = Find-CommandPath @("python", "python3", "python3.11", "py")
if (-not $Python) {
    $Python = Find-ExistingPath @(
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python312\python.exe"
    )
}

$Node = Find-CommandPath @("node")
if (-not $Node) {
    $Node = Find-ExistingPath @(
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe",
        "$env:ProgramFiles\nodejs\node.exe"
    )
}

Write-LaunchLog "==== Fund AI foreground launcher ===="
if (-not $Python) {
    Write-LaunchLog "[ERROR] Python was not found. Install Python 3.11+."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-LaunchLog "[OK] Python: $Python"

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
}

Write-LaunchLog "[1/4] Checking backend dependencies..."
& $Python -c "import fastapi, sqlalchemy, uvicorn, apscheduler, loguru, openai, akshare"
if ($LASTEXITCODE -ne 0) {
    Write-LaunchLog "[INFO] Installing backend runtime dependencies..."
    & $Python -m pip install -r requirements-runtime.txt
    if ($LASTEXITCODE -ne 0) {
        Write-LaunchLog "[ERROR] Dependency installation failed."
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Write-LaunchLog "[2/4] Initializing database..."
& $Python -c "import sys; sys.path.insert(0, '.'); from backend.database import init_db; init_db(); print('database initialized')"
if ($LASTEXITCODE -ne 0) {
    Write-LaunchLog "[ERROR] Database initialization failed."
    Read-Host "Press Enter to exit"
    exit 1
}
& $Python "scripts\repair_mojibake.py"

Write-LaunchLog "[3/4] Checking frontend build..."
if (-not (Test-Path "frontend\dist\index.html")) {
    if (-not $Node) {
        Write-LaunchLog "[ERROR] Node.js was not found and frontend\dist is missing."
        Read-Host "Press Enter to exit"
        exit 1
    }
    Push-Location "frontend"
    & $Node "node_modules\vite\bin\vite.js" build
    $buildCode = $LASTEXITCODE
    Pop-Location
    if ($buildCode -ne 0) {
        Write-LaunchLog "[ERROR] Frontend build failed."
        Read-Host "Press Enter to exit"
        exit 1
    }
}

$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($existing) {
    Write-LaunchLog "[OK] Existing backend found. Opening $Url"
    if (-not $NoBrowser) {
        Start-Process $Url
    }
    Write-Host "Service is already running. Use stop.bat to stop it."
    Read-Host "Press Enter to close this window"
    exit 0
}

if (-not $NoBrowser) {
    $OpenScript = @"
`$url = '$Url'
for (`$i = 1; `$i -le 45; `$i++) {
    Start-Sleep -Seconds 1
    try {
        `$health = Invoke-RestMethod "`$url/api/health" -TimeoutSec 2
        if (`$health.status -eq 'ok') {
            Start-Process `$url
            exit 0
        }
    } catch {}
}
"@
    $OpenScriptPath = Join-Path $env:TEMP "fund-ai-open-browser.ps1"
    Set-Content -Path $OpenScriptPath -Value $OpenScript -Encoding ASCII
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$OpenScriptPath`"" -WindowStyle Hidden
}

Write-LaunchLog "[4/4] Starting backend in this window..."
Write-Host ""
Write-Host "Keep this window open while using Fund AI. Close it or run stop.bat to stop the service."
Write-Host ""
& $Python "scripts\run_backend.py"
