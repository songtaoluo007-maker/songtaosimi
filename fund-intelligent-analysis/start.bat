@echo off
chcp 65001 >nul
echo ==========================================
echo   私人基金量化系统 - 启动中...
echo ==========================================

cd /d "%~dp0"

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Node.js，请先安装Node.js 20+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

:: 创建.env（如果不存在）
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [提示] 已创建 .env 配置文件
        echo [重要] 请编辑 .env 文件，填入你的 DeepSeek API Key
    )
)

:: 创建数据目录
if not exist "data" mkdir data
if not exist "data\logs" mkdir data\logs
if not exist "data\ocr_temp" mkdir data\ocr_temp

:: 安装后端依赖
echo [1/5] 检查后端Python依赖...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    echo 请尝试手动运行: pip install -r requirements.txt
    pause
    exit /b 1
)
echo       后端依赖已就绪

:: 安装前端依赖
echo [2/5] 检查前端Node依赖...
if not exist "frontend\node_modules" (
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [错误] 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
)
echo       前端依赖已就绪

:: 初始化数据库
echo [3/5] 初始化数据库...
python -c "import sys; sys.path.insert(0, '.'); from backend.database import init_db; init_db(); print('数据库初始化完成')"
if errorlevel 1 (
    echo [错误] 数据库初始化失败
    pause
    exit /b 1
)

:: 构建前端
echo [4/5] 构建前端...
cd frontend
call npm run build
if errorlevel 1 (
    echo [警告] 前端构建失败，将使用开发模式
    cd ..
    goto :dev_mode
)
cd ..
echo       前端构建完成

:: 启动后端（后台运行）
echo [5/5] 启动服务...
start "fund-quant-backend" /min python -c "import sys; sys.path.insert(0, '.'); from backend.main import app; from backend.config import settings; import uvicorn; uvicorn.run(app, host=settings.BACKEND_HOST, port=settings.BACKEND_PORT)"

:: 等待后端就绪
timeout /t 3 /nobreak >nul

echo.
echo ==========================================
echo   系统启动完成！
echo   前端地址: http://localhost:8000
echo   API文档:  http://localhost:8000/docs
echo ==========================================
echo.
echo 按任意键打开浏览器...
pause >nul
start http://localhost:8000
echo.
echo 关闭此窗口不会停止服务
echo 如需停止，请运行 stop.bat
pause >nul
exit /b 0

:dev_mode
echo [开发模式] 分别启动前后端...
start "fund-quant-backend" /min python -c "import sys; sys.path.insert(0, '.'); from backend.main import app; from backend.config import settings; import uvicorn; uvicorn.run(app, host=settings.BACKEND_HOST, port=settings.BACKEND_PORT)"
cd frontend
start "fund-quant-frontend" /min cmd /c npx vite --host 127.0.0.1 --port 3000
cd ..
echo.
echo ==========================================
echo   系统启动完成（开发模式）！
echo   前端地址: http://localhost:3000
echo   后端API:  http://localhost:8000/docs
echo ==========================================
pause >nul
