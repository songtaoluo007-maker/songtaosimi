# 基金智能分析 — Windows 桌面应用打包脚本
# 用法: powershell -File scripts/build_desktop.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  基金智能分析 — 桌面应用打包" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查依赖
Write-Host "[1/5] 检查依赖..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "错误: 未找到 Python，请安装 Python 3.11+" -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $($python.Source)" -ForegroundColor Green

# 2. 安装打包依赖
Write-Host "[2/5] 安装打包依赖..." -ForegroundColor Yellow
python -m pip install pyinstaller pywebview 2>&1 | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) {
    Write-Host "打包依赖安装失败！请检查 pip 输出" -ForegroundColor Red
    exit 1
}
Write-Host "  依赖就绪" -ForegroundColor Green

# 3. 构建前端
Write-Host "[3/5] 构建前端..." -ForegroundColor Yellow
if (Test-Path "frontend\package.json") {
    Push-Location frontend
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        npm install 2>&1 | Select-Object -Last 2
        npx vite build 2>&1 | Select-Object -Last 3
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  前端构建失败，但继续打包（使用已有 dist）" -ForegroundColor Yellow
        } else {
            Write-Host "  前端构建完成" -ForegroundColor Green
        }
    } else {
        Write-Host "  未检测到 Node.js，使用已有 dist/" -ForegroundColor Yellow
    }
    Pop-Location
} else {
    Write-Host "  未找到前端目录，跳过" -ForegroundColor Yellow
}

# 4. PyInstaller 打包
Write-Host "[4/5] PyInstaller 打包中（约 3-8 分钟）..." -ForegroundColor Yellow
python -m PyInstaller scripts/fund_ai.spec --clean --noconfirm 2>&1 | Select-Object -Last 10
if ($LASTEXITCODE -ne 0) {
    Write-Host "打包失败！请检查上方错误信息" -ForegroundColor Red
    exit 1
}
Write-Host "  打包完成" -ForegroundColor Green

# 5. 检查产物
Write-Host "[5/5] 检查产物..." -ForegroundColor Yellow
$exe = "dist\基金智能分析.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "  生成: $exe ($size MB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  打包成功！" -ForegroundColor Cyan
    Write-Host "  可执行文件: dist\基金智能分析.exe" -ForegroundColor White
    Write-Host "  双击即可运行，无需安装 Python" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Cyan
} else {
    Write-Host "  未找到生成的 exe，打包可能失败" -ForegroundColor Red
    exit 1
}
