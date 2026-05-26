"""
AI 顾问 API — V2（含 AI 生成体验优化）

V2 改动汇总：
- BUG 修复：v1 在 get_advice_backtest 中用 MarketSnapshot/Holding 但未 import → NameError
- BUG 修复：v1 backtest 中的 best_view 是死代码，删除
- 新增 stale timeout：running 状态超过 STALE_THRESHOLD 自动 reset 为 failed，
  解决 v1 "线程崩了之后永远 '已有AI建议正在生成'，必须重启进程" 的问题
- 新增 step_done / step_total 字段：v2 的 AiAdvisorService 会汇报真实步骤进度，
  前端可以基于真实数字而非估算来更新进度条
- _run_generation_job 完成后会校验 advice 是否真的存到今天，若否标 result.error
- 暴露 /advice/generate/reset 端点：用户在前端可手动解锁卡死的任务
- 切换到 v2 版 AiAdvisorService（覆盖之前的 v2，整合所有改动）
"""
import json
import threading
import time
import uuid
from datetime import date, datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import SessionLocal, get_db
from backend.config import settings
from backend.models.ai_advice import AiAdvice
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot

router = APIRouter(prefix="/api/ai", tags=["AI顾问"])

# 任务存活超时（秒）— 超过这个时间还停在 running 状态，说明 worker 线程已挂
STALE_THRESHOLD = 300


_JOB_LOCK = threading.Lock()
_GENERATION_JOB = {
    "job_id": "",
    "status": "idle",
    "step": "空闲",
    "message": "",
    "refresh": False,
    "started_at": None,
    "started_at_ts": 0.0,
    "finished_at": None,
    "step_done": 0,
    "step_total": 0,
    "result": None,
    "error": "",
}


def _job_snapshot() -> dict:
    with _JOB_LOCK:
        return dict(_GENERATION_JOB)


def _set_job(**kwargs) -> None:
    with _JOB_LOCK:
        _GENERATION_JOB.update(kwargs)


def _maybe_reset_stale_job() -> None:
    """v2 关键：上次任务线程崩溃时，把残留的 running 状态自动 reset，避免永久卡死。"""
    snap = _job_snapshot()
    if snap.get("status") not in {"queued", "running"}:
        return
    started_ts = snap.get("started_at_ts") or 0
    if started_ts and time.time() - started_ts > STALE_THRESHOLD:
        _set_job(
            status="failed",
            step="failed",
            message=f"任务超过 {STALE_THRESHOLD}s 未完成，已自动 reset",
            error="stale_timeout",
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )


def _run_generation_job(job_id: str, refresh: bool) -> None:
    db = SessionLocal()
    try:
        def _progress(payload):
            """V2：进度回调接收 dict（含 step_done/step_total），把真实进度透给前端。"""
            if isinstance(payload, dict):
                _set_job(
                    status="running",
                    step=payload.get("step", ""),
                    message=payload.get("message", ""),
                    step_done=payload.get("step_done", _GENERATION_JOB.get("step_done", 0)),
                    step_total=payload.get("step_total", _GENERATION_JOB.get("step_total", 0)),
                )
            else:
                _set_job(status="running", step="running", message=str(payload))

        _set_job(
            status="running",
            step="refreshing_data" if refresh else "using_cached_data",
            message="正在准备持仓、行情、新闻数据...",
            step_done=0,
            step_total=7 if refresh else 1,
        )

        from backend.services.ai_advisor import AiAdvisorService

        service = AiAdvisorService(db)
        result = (
            service.generate_close_advice(progress_cb=_progress)
            if refresh
            else service.generate_advice(progress_cb=_progress)
        )

        if result.get("error"):
            _set_job(
                status="failed",
                step="failed",
                message=result.get("error", "AI建议生成失败"),
                error=result.get("error", "AI建议生成失败"),
                finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                result=result,
            )
            return

        # V2：完成前校验 — advice 必须真的写到今天
        advice_date = result.get("advice_date")
        advice_id = result.get("advice_id")
        if not advice_id or advice_date != date.today().isoformat():
            _set_job(
                status="failed",
                step="failed",
                message="AI 调用完成但未生成今日记录（可能数据库写入异常）",
                error="missing_today_advice",
                finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                result=result,
            )
            return

        _set_job(
            status="completed",
            step="completed",
            message="AI 建议已生成",
            error="",
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            result=result,
        )
    except Exception as exc:
        _set_job(
            status="failed",
            step="failed",
            message=str(exc),
            error=str(exc),
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    finally:
        db.close()


@router.get("/advice")
def list_advices(limit: int = 30, db: Session = Depends(get_db)):
    advices = db.query(AiAdvice).order_by(AiAdvice.advice_date.desc()).limit(limit).all()
    return [a.to_dict() for a in advices]


@router.get("/advice/latest")
def get_latest_advice(db: Session = Depends(get_db)):
    advice = (
        db.query(AiAdvice)
        .order_by(AiAdvice.advice_date.desc(), AiAdvice.advice_time.desc())
        .first()
    )
    if not advice:
        return {"message": "暂无AI建议", "advice": None}
    result = advice.to_dict()
    if advice.structured_output:
        try:
            result["structured"] = json.loads(advice.structured_output)
        except (json.JSONDecodeError, TypeError):
            result["structured"] = None
    return result


@router.get("/advice/{advice_id}/structured")
def get_structured_advice(advice_id: int, db: Session = Depends(get_db)):
    advice = db.query(AiAdvice).filter(AiAdvice.id == advice_id).first()
    if not advice:
        raise HTTPException(status_code=404, detail="建议不存在")
    result = advice.to_dict()
    if advice.structured_output:
        try:
            result["structured"] = json.loads(advice.structured_output)
        except (json.JSONDecodeError, TypeError):
            result["structured"] = None
    if advice.context_json:
        try:
            result["context"] = json.loads(advice.context_json)
        except (json.JSONDecodeError, TypeError):
            result["context"] = None
    return result


@router.get("/advice/generate/status")
def get_generation_status():
    # 每次拉取时检查 stale，避免前端轮询不到 reset
    _maybe_reset_stale_job()
    return _job_snapshot()


@router.post("/advice/generate/reset")
def reset_generation_status():
    """V2 新增：手动 reset 卡死的生成任务（前端有 '强制解锁' 按钮可调用）"""
    _set_job(
        status="idle",
        step="空闲",
        message="已手动 reset",
        error="",
        step_done=0,
        step_total=0,
    )
    return {"message": "已 reset", "status": "idle"}


def _start_generation_job(refresh: bool = False):
    _maybe_reset_stale_job()
    current = _job_snapshot()
    if current.get("status") in {"queued", "running"}:
        return current | {"accepted": False, "message": "AI 建议正在生成中"}

    job_id = uuid.uuid4().hex
    _set_job(
        job_id=job_id,
        status="queued",
        step="queued",
        message="AI 建议生成已入队",
        refresh=refresh,
        started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        started_at_ts=time.time(),
        finished_at=None,
        step_done=0,
        step_total=7 if refresh else 1,
        result=None,
        error="",
    )
    worker = threading.Thread(target=_run_generation_job, args=(job_id, refresh), daemon=True)
    worker.start()
    return _job_snapshot() | {"accepted": True}


@router.post("/advice/generate-async")
def generate_advice_async(refresh: bool = Query(False)):
    return _start_generation_job(refresh)


@router.put("/advice/{advice_id}/read")
def mark_advice_read(advice_id: int, db: Session = Depends(get_db)):
    advice = db.query(AiAdvice).filter(AiAdvice.id == advice_id).first()
    if not advice:
        raise HTTPException(status_code=404, detail="建议不存在")
    advice.is_read = True
    db.commit()
    return {"message": "已标记为已读"}


class AdoptRequest(BaseModel):
    adopted: bool
    note: str = ""


@router.put("/advice/{advice_id}/adopt")
def adopt_advice(advice_id: int, body: AdoptRequest, db: Session = Depends(get_db)):
    advice = db.query(AiAdvice).filter(AiAdvice.id == advice_id).first()
    if not advice:
        raise HTTPException(status_code=404, detail="建议不存在")
    advice.adopted = body.adopted
    advice.adopted_at = datetime.now()
    advice.adoption_note = body.note or ""
    db.commit()
    return {"message": "已采纳" if body.adopted else "已忽略", "adopted": body.adopted}


@router.get("/advice/backtest")
def get_advice_backtest(db: Session = Depends(get_db)):
    """AI 建议回测：对比组合 vs 沪深300，分市场观点统计超额收益。"""
    advices = db.query(AiAdvice).order_by(AiAdvice.advice_date.asc()).all()
    if len(advices) < 2:
        return {"message": "建议数量不足（至少需要2条）", "points": [], "summary": {}}

    hs300 = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == "000300.SH",
            MarketSnapshot.snapshot_type == "index",
        )
        .order_by(MarketSnapshot.snapshot_date.asc())
        .all()
    )
    hs300_map: dict[str, float] = {}
    for s in hs300:
        hs300_map[str(s.snapshot_date)] = float(s.price or 0)
    hs300_start = next(iter(hs300_map.values()), 0)

    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)

    advice_dates = [a.advice_date for a in advices if a.advice_date]
    fund_snaps_all = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.snapshot_type == "fund",
            MarketSnapshot.snapshot_date.in_(advice_dates),
        )
        .all()
    )
    snaps_by_date: dict = {}
    for s in fund_snaps_all:
        snaps_by_date.setdefault(s.snapshot_date, {})[s.symbol.replace("fund_", "")] = s

    total_adopted = sum(1 for a in advices if a.adopted is True)
    points = []
    cumulative_adopted = 0
    for i, advice in enumerate(advices, start=1):
        d = advice.advice_date
        if not d:
            continue
        if advice.adopted is True:
            cumulative_adopted += 1

        snap_map = snaps_by_date.get(d, {})
        day_value = 0.0
        for h in holdings:
            snap = snap_map.get(h.fund_code)
            if snap and snap.price:
                day_value += float(h.shares or 0) * float(snap.price)
            else:
                day_value += float(h.current_value or 0)

        portfolio_return = (
            (day_value - total_cost) / total_cost * 100 if total_cost > 0 else 0
        )
        hs300_val = hs300_map.get(str(d))
        benchmark_return = (
            (hs300_val - hs300_start) / hs300_start * 100
            if hs300_val and hs300_start
            else 0
        )

        points.append({
            "date": str(d),
            "portfolio_return": round(portfolio_return, 2),
            "benchmark_return": round(benchmark_return, 2),
            "excess_return": round(portfolio_return - benchmark_return, 2),
            "market_view": advice.market_view,
            "adoption_rate": round(cumulative_adopted / i * 100, 1) if i else 0,
            "advice_count": i,
        })

    view_returns: dict[str, list[float]] = {"bullish": [], "bearish": [], "neutral": []}
    for p in points:
        view_returns.setdefault(p["market_view"] or "neutral", []).append(p["excess_return"])
    view_performance = {
        k: round(sum(v) / len(v), 2) if v else 0 for k, v in view_returns.items()
    }

    last = points[-1] if points else {"portfolio_return": 0, "benchmark_return": 0, "excess_return": 0}
    summary = {
        "total_advices": len(advices),
        "adopted_count": total_adopted,
        "ignored_count": sum(1 for a in advices if a.adopted is False),
        "portfolio_return": last["portfolio_return"],
        "benchmark_return": last["benchmark_return"],
        "excess_return": last["excess_return"],
        "view_performance": view_performance,
    }

    return {"points": points, "summary": summary}


@router.post("/notify/test")
def test_feishu_notification():
    from backend.services.notification import _send_feishu

    if not settings.FEISHU_WEBHOOK_URL:
        return {"success": False, "error": "飞书 Webhook 未配置"}

    mock = {
        "advice_date": "测试消息",
        "market_view": "neutral",
        "risk_level": "low",
        "actions": [],
        "opportunities": [],
        "overall_suggestion": "基金智能分析系统的测试消息，飞书通知配置正常。",
    }
    return _send_feishu(mock)


@router.post("/notify/send-latest")
def send_latest_to_feishu(db: Session = Depends(get_db)):
    from backend.services.notification import send_advice_notification

    if not settings.FEISHU_WEBHOOK_URL:
        return {"success": False, "error": "飞书 Webhook 未配置"}

    advice = (
        db.query(AiAdvice)
        .order_by(AiAdvice.advice_date.desc(), AiAdvice.advice_time.desc())
        .first()
    )
    if not advice:
        return {"success": False, "error": "暂无AI建议，请先生成"}

    return send_advice_notification(advice.to_dict())
