"""
私人基金量化系统 - FastAPI主入口
"""
import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

# 确保项目根目录在sys.path中
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import settings
from backend.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动和关闭"""
    # 启动时
    logger.info("正在初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")

    # 复制.env.example为.env（如果不存在）
    env_file = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"
    if not env_file.exists() and env_example.exists():
        import shutil
        shutil.copy(env_example, env_file)
        logger.info("已创建 .env 配置文件，请根据需要修改")

    # 启动调度器
    try:
        from backend.scheduler.setup import init_scheduler
        init_scheduler()
        logger.info("定时任务调度器已启动")
    except Exception as e:
        logger.warning(f"调度器启动失败（不影响手动操作）: {e}")

    logger.info(f"系统启动完成 - 后端端口: {settings.BACKEND_PORT}")

    yield

    # 关闭时
    try:
        from backend.scheduler.setup import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    logger.info("系统已关闭")


# 配置loguru
logger.remove()
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)
logger.add(
    os.path.join(settings.LOG_DIR, "app_{time:YYYY-MM-DD}.log"),
    rotation="1 day",
    retention="30 days",
    level="INFO",
    encoding="utf-8",
)

# 创建FastAPI应用
app = FastAPI(
    title="私人基金量化系统",
    description="本地部署的私人基金量化分析系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS配置 - 允许前端开发服务器跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
from backend.api.fund import router as fund_router
from backend.api.holding import router as holding_router
from backend.api.trade import router as trade_router
from backend.api.market import router as market_router
from backend.api.news import router as news_router
from backend.api.ai_advice import router as ai_router
from backend.api.ocr import router as ocr_router
from backend.api.dashboard import router as dashboard_router
from backend.api.settings import router as settings_router
from backend.api.fund_group import router as group_router

app.include_router(fund_router)
app.include_router(holding_router)
app.include_router(trade_router)
app.include_router(market_router)
app.include_router(news_router)
app.include_router(ai_router)
app.include_router(ocr_router)
app.include_router(dashboard_router)
app.include_router(settings_router)
app.include_router(group_router)


@app.get("/api/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "has_ai_key": bool(settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_KEY != "your_deepseek_api_key_here"),
    }


# 托管前端静态文件（构建后） - 必须放在所有API路由之后
frontend_dist = ROOT_DIR / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


    @app.get("/")
    def serve_frontend_root():
        return FileResponse(frontend_dist / "index.html")


    @app.get("/{full_path:path}")
    def serve_frontend_spa(full_path: str):
        target = frontend_dist / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )
