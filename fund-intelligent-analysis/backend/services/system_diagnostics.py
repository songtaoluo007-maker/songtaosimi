"""
System diagnostics and data freshness checks.

This module is intentionally local-only: it inspects the SQLite database,
runtime configuration, scheduler state, and log files without making network
requests. The goal is to make data reliability visible inside the app.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.fund import Fund  # noqa: F401 - register relationships
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.models.news import News
from backend.models.trade import Trade  # noqa: F401 - register relationships


def _sqlite_path() -> Path | None:
    if not settings.DATABASE_URL.startswith("sqlite"):
        return None
    parsed = urlparse(settings.DATABASE_URL)
    if parsed.path:
        return Path(unquote(parsed.path.lstrip("/")))
    return None


def _latest_snapshot(db: Session, snapshot_type: str) -> dict:
    row = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.snapshot_type == snapshot_type)
        .order_by(
            MarketSnapshot.snapshot_date.desc(),
            MarketSnapshot.snapshot_time.desc(),
            MarketSnapshot.id.desc(),
        )
        .first()
    )
    if not row:
        return {
            "snapshot_type": snapshot_type,
            "latest_date": None,
            "latest_time": None,
            "latest_at": None,
            "count_on_latest_date": 0,
        }

    count = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.snapshot_type == snapshot_type,
            MarketSnapshot.snapshot_date == row.snapshot_date,
        )
        .count()
    )
    latest_at = None
    if row.snapshot_date and row.snapshot_time:
        latest_at = datetime.combine(row.snapshot_date, row.snapshot_time)

    return {
        "snapshot_type": snapshot_type,
        "latest_date": row.snapshot_date.isoformat() if row.snapshot_date else None,
        "latest_time": str(row.snapshot_time) if row.snapshot_time else None,
        "latest_at": latest_at.strftime("%Y-%m-%d %H:%M:%S") if latest_at else None,
        "count_on_latest_date": count,
        "sample_name": row.to_dict().get("name"),
    }


def _snapshot_check(
    title: str,
    item: dict,
    trading_day: bool,
    max_rest_days: int = 10,
) -> dict:
    latest_date = item.get("latest_date")
    count = item.get("count_on_latest_date", 0)
    if not latest_date:
        return {
            "key": item["snapshot_type"],
            "title": title,
            "status": "critical",
            "message": "暂无数据",
            "detail": "请在行情监控或设置页手动刷新采集任务。",
        }

    parsed_date = date.fromisoformat(latest_date)
    today = date.today()
    if trading_day and parsed_date != today:
        return {
            "key": item["snapshot_type"],
            "title": title,
            "status": "warning",
            "message": f"最新数据停留在 {latest_date}",
            "detail": "交易日应优先使用当天行情，建议立即刷新。",
        }
    if not trading_day and (today - parsed_date).days > max_rest_days:
        return {
            "key": item["snapshot_type"],
            "title": title,
            "status": "warning",
            "message": f"最近可用数据距今 {(today - parsed_date).days} 天",
            "detail": "休市期间允许展示最近交易日数据，但时间跨度过长会降低AI建议可信度。",
        }
    if count <= 0:
        return {
            "key": item["snapshot_type"],
            "title": title,
            "status": "warning",
            "message": "最新日期无有效记录",
            "detail": "数据表存在日期但缺少明细。",
        }
    return {
        "key": item["snapshot_type"],
        "title": title,
        "status": "ok",
        "message": f"{latest_date} {item.get('latest_time') or ''}，{count} 条",
        "detail": "",
    }


def _news_status(db: Session) -> tuple[dict, dict]:
    latest = (
        db.query(News)
        .filter(News.publish_time.isnot(None))
        .order_by(News.publish_time.desc(), News.id.desc())
        .first()
    )
    if not latest:
        latest = db.query(News).order_by(News.created_at.desc(), News.id.desc()).first()

    lookback_start = datetime.now() - timedelta(days=settings.AI_NEWS_LOOKBACK_DAYS)
    recent_count = db.query(News).filter(News.publish_time >= lookback_start).count()
    source_rows = (
        db.query(News.source, func.count(News.id))
        .filter(News.publish_time >= lookback_start)
        .group_by(News.source)
        .order_by(func.count(News.id).desc())
        .limit(6)
        .all()
    )
    sentiment_rows = (
        db.query(News.sentiment, func.count(News.id))
        .filter(News.publish_time >= lookback_start)
        .group_by(News.sentiment)
        .all()
    )

    latest_time = latest.publish_time if latest and latest.publish_time else None
    hours_old = None
    if latest_time:
        hours_old = round((datetime.now() - latest_time).total_seconds() / 3600, 1)

    status = "ok"
    message = "新闻数据正常"
    detail = ""
    if not latest:
        status = "critical"
        message = "暂无新闻"
        detail = "请立即刷新新闻，AI建议会缺少情绪面输入。"
    elif hours_old is None:
        status = "warning"
        message = "新闻缺少发布时间"
        detail = "建议刷新新闻源以便排序和新鲜度判断。"
    elif hours_old > 12:
        status = "warning"
        message = f"最新新闻距今约 {hours_old} 小时"
        detail = "成熟金融产品需要保持盘前、盘中、盘后资讯连续更新。"

    return (
        {
            "latest_title": latest.title if latest else "",
            "latest_source": latest.source if latest else "",
            "latest_time": latest_time.strftime("%Y-%m-%d %H:%M:%S") if latest_time else None,
            "hours_old": hours_old,
            "recent_count": recent_count,
            "lookback_days": settings.AI_NEWS_LOOKBACK_DAYS,
            "source_mix": [{"source": source or "未知", "count": count} for source, count in source_rows],
            "sentiment_mix": {sentiment or "neutral": count for sentiment, count in sentiment_rows},
        },
        {
            "key": "news",
            "title": "财经新闻",
            "status": status,
            "message": message if latest else "暂无新闻",
            "detail": detail,
        },
    )


def _log_status() -> list[dict]:
    log_dir = Path(settings.LOG_DIR)
    names = ["backend_stderr.log", "desktop_backend_stderr.log", "desktop_app.log"]
    items = []
    for name in names:
        path = log_dir / name
        items.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                if path.exists()
                else None,
            }
        )
    return items


def build_diagnostics(db: Session) -> dict:
    try:
        from backend.services.market_collector import is_trading_day

        trading_day = bool(is_trading_day())
    except Exception:
        trading_day = date.today().weekday() < 5

    snapshots = {
        "index": _latest_snapshot(db, "index"),
        "sector": _latest_snapshot(db, "sector"),
        "concept": _latest_snapshot(db, "concept"),
        "global": _latest_snapshot(db, "global"),
        "fund": _latest_snapshot(db, "fund"),
    }
    news, news_check = _news_status(db)
    active_holdings = db.query(Holding).filter(Holding.is_active == True).count()
    total_holdings = db.query(Holding).count()

    db_path = _sqlite_path()
    db_info = {
        "url": settings.DATABASE_URL,
        "path": str(db_path) if db_path else "",
        "exists": db_path.exists() if db_path else False,
        "size_mb": round(db_path.stat().st_size / 1024 / 1024, 2) if db_path and db_path.exists() else 0,
    }

    checks = [
        {
            "key": "database",
            "title": "本地数据库",
            "status": "ok" if db_info["exists"] else "critical",
            "message": f"{db_info['size_mb']} MB" if db_info["exists"] else "数据库文件不存在",
            "detail": db_info["path"],
        },
        {
            "key": "api_key",
            "title": "AI API Key",
            "status": "ok"
            if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_KEY != "your_deepseek_api_key_here"
            else "warning",
            "message": "已配置" if settings.DEEPSEEK_API_KEY else "未配置",
            "detail": "未配置时仍可看行情，但不能生成AI建议。",
        },
        {
            "key": "holdings",
            "title": "基金持仓",
            "status": "ok" if active_holdings > 0 else "warning",
            "message": f"持仓 {active_holdings} 只，总记录 {total_holdings} 条",
            "detail": "",
        },
        _snapshot_check("A股指数", snapshots["index"], trading_day),
        _snapshot_check("行业板块", snapshots["sector"], trading_day),
        _snapshot_check("概念板块", snapshots["concept"], trading_day),
        _snapshot_check("全球市场", snapshots["global"], trading_day, max_rest_days=3),
        _snapshot_check("基金估值", snapshots["fund"], trading_day),
        news_check,
    ]

    ocr_temp = Path(settings.OCR_TEMP_DIR)
    try:
        __import__("rapidocr_onnxruntime")
        ocr_ok = True
        ocr_detail = str(ocr_temp)
    except Exception as exc:
        ocr_ok = False
        ocr_detail = str(exc)
    checks.append(
        {
            "key": "ocr",
            "title": "截图OCR",
            "status": "ok" if ocr_ok and ocr_temp.exists() else "warning",
            "message": "可用" if ocr_ok else "OCR依赖不可用",
            "detail": ocr_detail,
        }
    )

    try:
        from backend.scheduler.setup import get_scheduler_status

        scheduler = get_scheduler_status()
        checks.append(
            {
                "key": "scheduler",
                "title": "定时任务",
                "status": "ok" if scheduler.get("status") == "running" else "warning",
                "message": f"运行中，{scheduler.get('job_count', 0)} 个任务"
                if scheduler.get("status") == "running"
                else "未运行",
                "detail": "",
            }
        )
    except Exception as exc:
        scheduler = {"status": "unknown", "jobs": [], "error": str(exc)}
        checks.append(
            {
                "key": "scheduler",
                "title": "定时任务",
                "status": "warning",
                "message": "状态读取失败",
                "detail": str(exc),
            }
        )

    counts = {
        "ok": sum(1 for item in checks if item["status"] == "ok"),
        "warning": sum(1 for item in checks if item["status"] == "warning"),
        "critical": sum(1 for item in checks if item["status"] == "critical"),
    }
    overall_status = "critical" if counts["critical"] else "warning" if counts["warning"] else "healthy"

    return {
        "status": overall_status,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_trading_day": trading_day,
        "market_context": "交易日" if trading_day else "休市期间，使用最近交易日数据复盘",
        "summary": counts,
        "checks": checks,
        "data_freshness": {
            "snapshots": snapshots,
            "news": news,
            "holdings": {
                "active_count": active_holdings,
                "total_count": total_holdings,
            },
        },
        "database": db_info,
        "logs": _log_status(),
        "scheduler": scheduler,
    }
