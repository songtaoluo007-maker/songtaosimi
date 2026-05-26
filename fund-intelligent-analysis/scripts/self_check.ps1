param(
    [int]$Port = 8011
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "data\logs"
$CheckDb = Join-Path $Root "data\self_check.db"
$OutLog = Join-Path $LogDir "self_check_backend_stdout.log"
$ErrLog = Join-Path $LogDir "self_check_backend_stderr.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

Write-Host "[1/5] Backend syntax check"
python -m compileall .\backend | Out-Host

Write-Host "[2/5] Frontend production build"
Push-Location frontend
npm run build | Out-Host
Pop-Location

Write-Host "[3/5] Start isolated backend on port $Port"
if (Test-Path $CheckDb) {
    Remove-Item -LiteralPath $CheckDb -Force
}
$env:DATABASE_URL = "sqlite:///$($CheckDb.Replace('\','/'))"
$env:BACKEND_PORT = "$Port"
$process = Start-Process -FilePath "python" -ArgumentList "scripts\run_backend.py" -WorkingDirectory $Root -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden -PassThru

try {
    $BaseUrl = "http://127.0.0.1:$Port"
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod "$BaseUrl/api/health" -TimeoutSec 2
            if ($health.status -eq "ok") {
                $ready = $true
                break
            }
        } catch {}
    }
    if (-not $ready) {
        throw "Self-check backend did not become ready"
    }

    Write-Host "[4/5] Auth flow check"
    $bootstrap = Invoke-RestMethod "$BaseUrl/api/auth/bootstrap-status" -TimeoutSec 5
    if ($bootstrap.has_user -ne $false) {
        throw "Expected fresh self-check database without users"
    }

    $unauthorized = $false
    try {
        Invoke-RestMethod "$BaseUrl/api/dashboard/overview" -TimeoutSec 5 | Out-Null
    } catch {
        $unauthorized = ($_.Exception.Response.StatusCode.value__ -eq 401)
    }
    if (-not $unauthorized) {
        throw "Protected API did not reject anonymous request"
    }

    $setupBody = @{ username = "owner"; password = "FundAI2026!"; display_name = "Self Check" } | ConvertTo-Json
    $setup = Invoke-RestMethod "$BaseUrl/api/auth/setup" -Method Post -Body $setupBody -ContentType "application/json" -TimeoutSec 5
    if (-not $setup.access_token) {
        throw "Setup did not return access token"
    }

    $headers = @{ Authorization = "Bearer $($setup.access_token)" }
    $me = Invoke-RestMethod "$BaseUrl/api/auth/me" -Headers $headers -TimeoutSec 5
    if ($me.username -ne "owner") {
        throw "Token could not read current user"
    }

    Write-Host "[5/5] Static shell check"
    $root = Invoke-WebRequest "$BaseUrl/" -UseBasicParsing -TimeoutSec 5
    if ($root.Headers["Cache-Control"] -notmatch "no-store") {
        throw "Frontend cache policy is not no-store"
    }

    Write-Host ""
    Write-Host "SELF CHECK PASSED" -ForegroundColor Green
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $CheckDb) {
        Remove-Item -LiteralPath $CheckDb -Force -ErrorAction SilentlyContinue
    }
    Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:\BACKEND_PORT -ErrorAction SilentlyContinue
}
