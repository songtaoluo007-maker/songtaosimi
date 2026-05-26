from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.config import settings

router = APIRouter(prefix="/api/settings", tags=["系统设置"])


@router.get("")
def get_settings():
    """获取当前配置（隐藏敏感信息）"""
    return {
        "deepseek_model": settings.DEEPSEEK_MODEL,
        "deepseek_base_url": settings.DEEPSEEK_BASE_URL,
        "has_api_key": settings.has_api_key,
        "market_collect_interval": settings.MARKET_COLLECT_INTERVAL_MINUTES,
        "fund_estimate_interval": settings.FUND_ESTIMATE_INTERVAL_MINUTES,
        "ai_advice_time": f"{settings.AI_ADVICE_HOUR:02d}:{settings.AI_ADVICE_MINUTE:02d}",
        "ai_advice_pre_refresh": settings.AI_ADVICE_PRE_REFRESH,
        "ai_news_lookback_days": settings.AI_NEWS_LOOKBACK_DAYS,
        "backend_host": settings.BACKEND_HOST,
        "backend_port": settings.BACKEND_PORT,
    }


@router.put("")
def update_settings():
    """更新配置（通过.env文件修改后重启生效）"""
    return {"message": "请修改 .env 文件后重启服务生效"}


@router.get("/scheduler-status")
def get_scheduler_status():
    """查看定时任务运行状态"""
    from backend.scheduler.setup import get_scheduler_status
    return get_scheduler_status()


@router.get("/diagnostics")
def get_diagnostics(db: Session = Depends(get_db)):
    """系统体检：数据新鲜度、调度器、AI Key、日志和数据库状态。"""
    from backend.services.system_diagnostics import build_diagnostics

    return build_diagnostics(db)


@router.post("/scheduler/trigger/{job_id}")
def trigger_job(job_id: str):
    """手动触发某个定时任务"""
    from backend.scheduler.setup import trigger_job_now
    result = trigger_job_now(job_id)
    return result
