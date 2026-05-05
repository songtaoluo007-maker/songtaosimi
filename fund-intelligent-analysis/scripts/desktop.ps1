param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

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

$PythonCandidates = New-Object System.Collections.ArrayList
foreach ($name in @("python", "python3", "py")) {
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

$RequiredImports = @("fastapi", "sqlalchemy", "uvicorn", "apscheduler", "loguru", "openai", "akshare", "rapidocr_onnxruntime")
$Python = $null
foreach ($candidate in $PythonCandidates) {
    if (Test-PythonImports $candidate $RequiredImports) {
        $Python = $candidate
        break
    }
}
if (-not $Python -and $PythonCandidates.Count -gt 0) {
    $Python = $PythonCandidates[0]
}
if (-not $Python) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("Python 3.11+ was not found.", "Fund AI", 0, 16) | Out-Null
    exit 1
}

if (-not (Test-PythonImports $Python @("webview"))) {
    & $Python -m pip install pywebview -q
}

if (-not (Test-Path "frontend\dist\index.html")) {
    $node = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    if (Test-Path $node) {
        Push-Location "frontend"
        & $node "node_modules\vite\bin\vite.js" build
        Pop-Location
    }
}

& $Python "scripts\desktop_app.py"
