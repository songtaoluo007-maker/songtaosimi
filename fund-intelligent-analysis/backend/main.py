"""
私人基金量化系统 - FastAPI主入口
"""
import shutil
import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

# 确保项目根目录在sys.path中
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _fix_akshare_data_path():
    """PyInstaller 打包后 akshare 找不到 file_fold/calendar.json，运行时修复。"""
    try:
        import akshare
        akshare_dir = Path(akshare.__file__).parent
        file_fold = akshare_dir / "file_fold"
        if not (file_fold / "calendar.json").exists():
            file_fold.mkdir(exist_ok=True)
            # 从项目 data 目录或 akshare 安装目录复制
            src = ROOT_DIR / "data" / "calendar.json"
            if not src.exists():
                # 尝试从 pip 安装目录找
                import importlib.metadata
                try:
                    dist = importlib.metadata.distribution("akshare")
                    dist_path = Path(str(dist._path))
                    src = dist_path / "file_fold" / "calendar.json"
                except Exception:
                    pass
            if src.exists():
                shutil.copy2(src, file_fold / "calendar.json")
                logger.info("已修复 AKShare 交易日历文件路径")
            else:
                logger.warning("未找到 akshare 交易日历文件，部分数据采集可能失败")
    except Exception as e:
        logger.warning(f"修复 AKShare 数据路径失败: {e}")


# 在调度器/服务导入前执行修复
_fix_akshare_data_path()

from backend.config import settings
from backend.database import init_db
from backend.middleware.auth import LocalAuthMiddleware
from backend.middleware.correlation import CorrelationMiddleware
from backend.middleware.rate_limit import RateLimitMiddleware


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

    # 首次运行时自动加密明文 API Key
    try:
        from backend.crypto import reencrypt_if_needed
        reencrypt_if_needed()
    except Exception as e:
        logger.debug(f"API Key 加密检查跳过: {e}")

    # 启动调度器
    try:
        from backend.scheduler.setup import init_scheduler
        init_scheduler()
        logger.info("定时任务调度器已启动")
    except Exception as e:
        logger.warning(f"调度器启动失败（不影响手动操作）: {e}")

    # 启动时立即刷新数据（后台线程池并行采集，不阻塞启动）
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _startup_refresh():
        logger.info("正在执行启动数据刷新（并行模式）...")
        from backend.scheduler.jobs import (
            job_collect_news,
            job_collect_global_index,
            job_collect_fund_nav,
        )

        tasks = {
            "新闻": job_collect_news,
            "全球指数": job_collect_global_index,
            "基金净值": job_collect_fund_nav,
        }

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(func): name for name, func in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result(timeout=60)
                    logger.info(f"启动采集 [{name}] 完成")
                except Exception as e:
                    logger.warning(f"启动采集 [{name}] 失败: {e}")

        logger.info("启动数据刷新完成")

    threading.Thread(target=_startup_refresh, daemon=True).start()

    logger.info(f"系统启动完成 - 后端端口: {settings.BACKEND_PORT}")

    yield

    # 关闭时
    try:
        from backend.scheduler.setup import shutdown_scheduler
        shutdown_scheduler()
    except Exception as e:
        logger.debug(f"调度器关闭失败（可能已退出）: {e}")
    logger.info("系统已关闭")


# 配置loguru
logger.remove()

# 控制台：人类可读格式
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)

# 文件日志：人类可读（日常排查）
logger.add(
    os.path.join(settings.LOG_DIR, "app_{time:YYYY-MM-DD}.log"),
    rotation="1 day",
    retention="30 days",
    level="INFO",
    encoding="utf-8",
)

# 文件日志：JSON 结构化（可接 ELK / OpenTelemetry）
logger.add(
    os.path.join(settings.LOG_DIR, "app_{time:YYYY-MM-DD}.jsonl"),
    rotation="1 day",
    retention="30 days",
    level="INFO",
    encoding="utf-8",
    serialize=True,
)

# 创建FastAPI应用
app = FastAPI(
    title="私人基金量化系统",
    description="本地部署的私人基金量化分析系统",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LocalAuthMiddleware)

# CORS配置 - 允许前端开发服务器跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理 — 统一错误响应格式
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"未处理异常 {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "服务器内部错误"},
    )

# 注册API路由
from backend.api.auth import router as auth_router
from backend.api.fund import router as fund_router
from backend.api.holding import router as holding_router
from backend.api.holding_metrics_v3 import router as holding_metrics_router
from backend.api.fund_manager_v3 import router as fund_manager_router
from backend.api.investment_plan_v3 import router as investment_plan_router
from backend.api.asset_allocation_v3 import router as asset_allocation_router
from backend.api.user_profile_v3 import router as user_profile_router
from backend.api.fund_fee_v3 import router as fund_fee_router
from backend.api.decision_review_v3 import router as decision_review_router
from backend.api.trade import router as trade_router
from backend.api.market import router as market_router
from backend.api.news import router as news_router
from backend.api.ai_advice import router as ai_router
from backend.api.ocr import router as ocr_router
from backend.api.dashboard import router as dashboard_router
from backend.api.settings import router as settings_router
from backend.api.fund_group import router as group_router
from backend.api.capital_flow import router as capital_flow_router
from backend.api.advice_review import router as review_router
from backend.api.risk_exposure import router as risk_exposure_router

app.include_router(capital_flow_router)
app.include_router(review_router)
app.include_router(risk_exposure_router)
app.include_router(auth_router)
app.include_router(fund_router)
app.include_router(holding_router)
app.include_router(holding_metrics_router)
app.include_router(fund_manager_router)
app.include_router(investment_plan_router)
app.include_router(asset_allocation_router)
app.include_router(user_profile_router)
app.include_router(fund_fee_router)
app.include_router(decision_review_router)
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
        "has_ai_key": settings.has_api_key,
    }


# 托管前端静态文件（构建后） - 必须放在所有API路由之后
frontend_dist = ROOT_DIR / "frontend" / "dist"
brand_assets = ROOT_DIR / "assets"
if brand_assets.exists():
    app.mount("/brand-assets", StaticFiles(directory=str(brand_assets)), name="brand-assets")

if frontend_dist.exists():
    no_store_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


    @app.get("/")
    def serve_frontend_root():
        return FileResponse(frontend_dist / "index.html", headers=no_store_headers)


    @app.get("/{full_path:path}")
    def serve_frontend_spa(full_path: str):
        target = frontend_dist / full_path
        if target.is_file():
            if target.name.lower() == "index.html":
                return FileResponse(target, headers=no_store_headers)
            return FileResponse(target)
        return FileResponse(frontend_dist / "index.html", headers=no_store_headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )
