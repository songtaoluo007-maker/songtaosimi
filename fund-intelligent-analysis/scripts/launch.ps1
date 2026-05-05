param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "data\logs"
$LaunchLog = Join-Path $LogDir "launcher.log"
$BackendStdoutLog = Join-Path $LogDir "backend_stdout.log"
$BackendStderrLog = Join-Path $LogDir "backend_stderr.log"
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

function Add-CandidatePath([System.Collections.ArrayList]$Candidates, $Path) {
    if ($Path -and (Test-Path $Path) -and -not $Candidates.Contains($Path)) {
        [void]$Candidates.Add($Path)
    }
}

function Test-PythonImports($PythonPath, $Imports) {
    $script = "import " + ($Imports -join ", ")
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PythonPath -c $script 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $oldPreference
    }
}

Write-LaunchLog "==== Fund AI launcher ===="

$PythonCandidates = New-Object System.Collections.ArrayList
foreach ($name in @("python", "python3", "python3.11", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        Add-CandidatePath $PythonCandidates $cmd.Source
    }
}
foreach ($path in @(
    "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "C:\Python311\python.exe",
    "C:\Python312\python.exe"
)) {
    Add-CandidatePath $PythonCandidates $path
}

$CoreImports = @("fastapi", "sqlalchemy", "uvicorn", "apscheduler", "loguru", "openai", "akshare")
$FullImports = $CoreImports + @("rapidocr_onnxruntime")
$Python = $null
foreach ($candidate in $PythonCandidates) {
    if (Test-PythonImports $candidate $FullImports) {
        $Python = $candidate
        break
    }
}
if (-not $Python) {
    foreach ($candidate in $PythonCandidates) {
        if (Test-PythonImports $candidate $CoreImports) {
            $Python = $candidate
            break
        }
    }
}
if (-not $Python -and $PythonCandidates.Count -gt 0) {
    $Python = $PythonCandidates[0]
}
if (-not $Python) {
    Write-LaunchLog "[ERROR] Python was not found. Install Python 3.11+ and enable Add python.exe to PATH."
    Write-LaunchLog "Download: https://www.python.org/downloads/"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-LaunchLog "[OK] Python: $Python"

$Node = Find-ExistingPath @(
    "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe",
    "$env:ProgramFiles\nodejs\node.exe"
)
if (-not $Node) {
    $Node = Find-CommandPath @("node")
}
if ($Node) {
    Write-LaunchLog "[OK] Node: $Node"
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-LaunchLog "[INFO] Created .env from .env.example."
}

Write-LaunchLog "[1/4] Checking backend dependencies..."
& $Python -c "import fastapi, sqlalchemy, uvicorn, apscheduler, loguru, openai, akshare, rapidocr_onnxruntime"
if ($LASTEXITCODE -ne 0) {
    Write-LaunchLog "[INFO] Missing backend dependencies. Installing requirements-runtime.txt..."
    & $Python -m pip install -r requirements-runtime.txt -q
    if ($LASTEXITCODE -ne 0) {
        Write-LaunchLog "[ERROR] Failed to install backend dependencies."
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
        Write-LaunchLog "[ERROR] Node.js was not found and frontend\dist does not exist. Install Node.js 20+."
        Write-LaunchLog "Download: https://nodejs.org/"
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

Write-LaunchLog "[4/4] Starting backend..."
$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($existing) {
    $healthy = $false
    try {
        $health = Invoke-RestMethod "$Url/api/health" -TimeoutSec 2
        $healthy = ($health.status -eq "ok")
    } catch {
        $healthy = $false
    }

    if ($healthy) {
        Write-LaunchLog "[OK] Existing backend is healthy."
    } else {
        Write-LaunchLog "[WARN] Port 8000 is occupied but health check failed. Restarting backend..."
        $pids = $existing | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pidToStop in $pids) {
            if ($pidToStop -and $pidToStop -ne $PID) {
                Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 1
        $existing = $null
    }
}

if (-not $existing) {
    $BackendScript = Join-Path $Root "scripts\run_backend.py"
    Start-Process `
        -FilePath $Python `
        -ArgumentList "`"$BackendScript`"" `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $BackendStdoutLog `
        -RedirectStandardError $BackendStderrLog `
        -WindowStyle Hidden
}

$ready = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod "$Url/api/health" -TimeoutSec 2
        if ($health.status -eq "ok") {
            $ready = $true
            break
        }
    } catch {
        Write-Host "Waiting for backend... $i/30"
    }
}

if (-not $ready) {
    Write-LaunchLog "[ERROR] Backend did not become ready in 30 seconds."
    Write-LaunchLog "Check log: $BackendStderrLog"
    if (Test-Path $BackendStderrLog) {
        Write-Host ""
        Write-Host "Recent backend error output:"
        Get-Content $BackendStderrLog -Tail 30
    }
    Read-Host "Press Enter to exit"
    exit 1
}

Write-LaunchLog "[OK] System is ready: $Url"
if (-not $NoBrowser) {
    Start-Process $Url
}

Write-Host ""
Write-Host "The system is running in the background. Use stop.bat to stop it."
Read-Host "Press Enter to close this window"
