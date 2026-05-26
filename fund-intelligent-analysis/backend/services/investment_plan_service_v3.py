"""
定投计划管理 + 微笑曲线 + 到期检查 — P1.1

核心能力：
1. CRUD：create/update/list/deactivate
2. 调度算法：根据 plan_type + day_of_period 计算"是否到期"
3. 微笑曲线：每期定投点 + NAV 曲线 + 摊薄成本水平线
4. 自动 diff 实际交易：把 trades 表里 source='auto_invest' 或同日同代码的买入关联到执行记录
5. 每日 9:00 检查应执行未执行的计划，触发飞书提醒
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable

from loguru import logger
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.investment_plan import InvestmentPlan, InvestmentPlanExecution
from backend.models.market_snapshot import MarketSnapshot
from backend.models.trade import Trade


# ──────────────── 计划 CRUD ────────────────

def create_plan(db: Session, payload: dict) -> InvestmentPlan:
    plan = InvestmentPlan(
        fund_code=payload["fund_code"],
        plan_name=payload.get("plan_name") or "",
        plan_type=payload["plan_type"],
        amount=payload["amount"],
        day_of_period=payload.get("day_of_period"),
        start_date=_parse_date(payload["start_date"]) or date.today(),
        end_date=_parse_date(payload.get("end_date")),
        target_amount=payload.get("target_amount"),
        auto_execute=bool(payload.get("auto_execute", False)),
        notes=payload.get("notes") or "",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    # 预生成未来 90 天的执行计划行，方便前端展示进度
    materialize_future_executions(db, plan, days_ahead=90)
    return plan


def update_plan(db: Session, plan_id: int, payload: dict) -> InvestmentPlan | None:
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == plan_id).first()
    if not plan:
        return None
    for field in ("plan_name", "plan_type", "amount", "day_of_period",
                  "target_amount", "auto_execute", "notes"):
        if field in payload and payload[field] is not None:
            setattr(plan, field, payload[field])
    if "start_date" in payload and payload["start_date"]:
        plan.start_date = _parse_date(payload["start_date"]) or plan.start_date
    if "end_date" in payload:
        plan.end_date = _parse_date(payload["end_date"])
    db.commit()
    db.refresh(plan)
    materialize_future_executions(db, plan, days_ahead=90)
    return plan


def deactivate_plan(db: Session, plan_id: int) -> bool:
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == plan_id).first()
    if not plan:
        return False
    plan.is_active = False
    db.commit()
    return True


def list_plans(db: Session, active_only: bool = True) -> list[dict]:
    query = db.query(InvestmentPlan)
    if active_only:
        query = query.filter(InvestmentPlan.is_active == True)
    plans = query.order_by(InvestmentPlan.id.desc()).all()

    fund_names = {
        f.fund_code: f.fund_name
        for f in db.query(Fund).filter(Fund.fund_code.in_([p.fund_code for p in plans])).all()
    }
    out = []
    for p in plans:
        data = p.to_dict()
        data["fund_name"] = fund_names.get(p.fund_code, "")
        stats = _plan_stats(db, p)
        data.update(stats)
        out.append(data)
    return out


# ──────────────── 调度算法 ────────────────

def _is_scheduled_day(plan: InvestmentPlan, target: date) -> bool:
    """判断某一天是否是该计划应执行日"""
    if plan.start_date and target < plan.start_date:
        return False
    if plan.end_date and target > plan.end_date:
        return False

    pt = (plan.plan_type or "").lower()
    if pt == "daily":
        return target.weekday() < 5  # 工作日
    if pt == "weekly":
        # day_of_period: 0=周一 ... 6=周日
        if plan.day_of_period is None:
            return False
        return target.weekday() == int(plan.day_of_period)
    if pt == "biweekly":
        if plan.day_of_period is None or not plan.start_date:
            return False
        if target.weekday() != int(plan.day_of_period):
            return False
        delta_days = (target - plan.start_date).days
        return delta_days >= 0 and (delta_days // 7) % 2 == 0
    if pt == "monthly":
        if plan.day_of_period is None:
            return False
        return target.day == int(plan.day_of_period)
    return False


def _iter_scheduled_dates(plan: InvestmentPlan, start: date, end: date) -> Iterable[date]:
    cursor = max(start, plan.start_date or start)
    last = end if not plan.end_date else min(end, plan.end_date)
    while cursor <= last:
        if _is_scheduled_day(plan, cursor):
            yield cursor
        cursor += timedelta(days=1)


def materialize_future_executions(db: Session, plan: InvestmentPlan,
                                  days_ahead: int = 90) -> int:
    """生成未来 N 天该计划的执行行（缺哪天补哪天），便于展示进度"""
    if not plan.is_active:
        return 0
    end = date.today() + timedelta(days=days_ahead)
    existing_dates = {
        row.scheduled_date for row in db.query(InvestmentPlanExecution)
        .filter(InvestmentPlanExecution.plan_id == plan.id).all()
    }
    inserted = 0
    for d in _iter_scheduled_dates(plan, date.today() - timedelta(days=1), end):
        if d in existing_dates:
            continue
        db.add(InvestmentPlanExecution(
            plan_id=plan.id,
            scheduled_date=d,
            executed=False,
        ))
        inserted += 1
    if inserted:
        db.commit()
    return inserted


def upcoming_executions(db: Session, days_ahead: int = 7) -> list[dict]:
    """未来 N 天应执行未执行的定投期"""
    today = date.today()
    end = today + timedelta(days=days_ahead)
    rows = (
        db.query(InvestmentPlanExecution)
        .join(InvestmentPlan)
        .filter(
            InvestmentPlanExecution.executed == False,
            InvestmentPlanExecution.scheduled_date >= today,
            InvestmentPlanExecution.scheduled_date <= end,
            InvestmentPlan.is_active == True,
        )
        .order_by(InvestmentPlanExecution.scheduled_date.asc())
        .all()
    )
    fund_names = {f.fund_code: f.fund_name for f in db.query(Fund).all()}
    out = []
    for r in rows:
        plan = r.plan
        out.append({
            **r.to_dict(),
            "fund_code": plan.fund_code,
            "fund_name": fund_names.get(plan.fund_code, ""),
            "plan_name": plan.plan_name or "",
            "plan_amount": float(plan.amount or 0),
        })
    return out


# ──────────────── 关联实际交易 ────────────────

def reconcile_with_trades(db: Session, plan: InvestmentPlan) -> int:
    """把 trades 表里同日同代码的买入交易关联到 plan_executions

    匹配规则：trade.fund_code == plan.fund_code && trade.trade_date == execution.scheduled_date
              && trade.trade_type == '买入'
    """
    executions = (
        db.query(InvestmentPlanExecution)
        .filter(InvestmentPlanExecution.plan_id == plan.id,
                InvestmentPlanExecution.executed == False)
        .all()
    )
    if not executions:
        return 0
    dates = [e.scheduled_date for e in executions]
    trades = (
        db.query(Trade)
        .filter(Trade.fund_code == plan.fund_code,
                Trade.trade_date.in_(dates),
                Trade.trade_type == "买入")
        .all()
    )
    by_date = {t.trade_date: t for t in trades}
    matched = 0
    for e in executions:
        t = by_date.get(e.scheduled_date)
        if not t:
            continue
        e.executed = True
        e.executed_at = datetime.now()
        e.trade_id = t.id
        e.actual_amount = t.amount
        e.actual_shares = t.shares
        e.nav_price = t.nav_price
        matched += 1
    if matched:
        db.commit()
    return matched


# ──────────────── 微笑曲线 ────────────────

def smile_curve_data(db: Session, plan_id: int) -> dict:
    """微笑曲线数据：每期定投 + NAV 历史 + 摊薄成本曲线"""
    plan = (
        db.query(InvestmentPlan)
        .filter(InvestmentPlan.id == plan_id)
        .first()
    )
    if not plan:
        return {"error": "计划不存在"}

    fund = db.query(Fund).filter(Fund.fund_code == plan.fund_code).first()
    executions = (
        db.query(InvestmentPlanExecution)
        .filter(InvestmentPlanExecution.plan_id == plan_id,
                InvestmentPlanExecution.executed == True)
        .order_by(InvestmentPlanExecution.scheduled_date.asc())
        .all()
    )

    # NAV 历史 — 用本地基金估值快照（symbol = fund_{code}），按日去重取最新时刻
    nav_rows = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.snapshot_type == "fund",
                MarketSnapshot.symbol == f"fund_{plan.fund_code}")
        .order_by(MarketSnapshot.snapshot_date.asc(),
                  MarketSnapshot.snapshot_time.asc())
        .all()
    )
    nav_by_day: dict[date, float] = {}
    for s in nav_rows:
        if s.snapshot_date:
            nav_by_day[s.snapshot_date] = float(s.price or 0)
    nav_series = [{"date": d.isoformat(), "nav": v}
                  for d, v in sorted(nav_by_day.items())]

    # 累计份额、成本、摊薄成本曲线
    cumulative_amount = 0.0
    cumulative_shares = 0.0
    cost_line = []
    execution_points = []
    for e in executions:
        amount = float(e.actual_amount or 0)
        shares = float(e.actual_shares or 0)
        cumulative_amount += amount
        cumulative_shares += shares
        avg_cost = cumulative_amount / cumulative_shares if cumulative_shares else 0
        cost_line.append({
            "date": e.scheduled_date.isoformat(),
            "average_cost": round(avg_cost, 4),
            "cumulative_cost": round(cumulative_amount, 2),
            "cumulative_shares": round(cumulative_shares, 4),
        })
        execution_points.append({
            "date": e.scheduled_date.isoformat(),
            "nav": float(e.nav_price or 0),
            "amount": amount,
            "shares": shares,
        })

    # 当前市值（用最新 NAV）
    latest_nav = nav_series[-1]["nav"] if nav_series else 0
    if not latest_nav:
        # 回退到 fund.latest_nav
        latest_nav = float(fund.latest_nav or 0) if fund else 0
    current_value = cumulative_shares * latest_nav
    current_pnl = current_value - cumulative_amount
    current_pnl_pct = (current_pnl / cumulative_amount * 100) if cumulative_amount > 0 else 0

    # 期数进度
    total_executions = len(executions)
    target_amount = float(plan.target_amount or 0)
    target_periods = int(target_amount / float(plan.amount)) if target_amount and plan.amount else 0

    return {
        "plan": plan.to_dict(),
        "fund_name": fund.fund_name if fund else "",
        "nav_series": nav_series,
        "execution_points": execution_points,
        "cost_line": cost_line,
        "summary": {
            "executed_periods": total_executions,
            "target_periods": target_periods,
            "cumulative_amount": round(cumulative_amount, 2),
            "cumulative_shares": round(cumulative_shares, 4),
            "average_cost": round(cumulative_amount / cumulative_shares, 4) if cumulative_shares > 0 else 0,
            "latest_nav": round(latest_nav, 4),
            "current_value": round(current_value, 2),
            "current_pnl": round(current_pnl, 2),
            "current_pnl_pct": round(current_pnl_pct, 2),
        },
    }


# ──────────────── 每日检查 + 提醒 ────────────────

def daily_check_and_alert(db: Session | None = None) -> dict:
    """每日 9:00 由 APScheduler 触发：检查今日应执行的定投，推飞书提醒"""
    own_db = db is None
    from backend.database import SessionLocal
    db = db or SessionLocal()
    try:
        # 先把每个 active 计划的未来执行行刷新一下（防止用户没操作系统时缺行）
        for plan in db.query(InvestmentPlan).filter(InvestmentPlan.is_active == True).all():
            materialize_future_executions(db, plan, days_ahead=90)
            reconcile_with_trades(db, plan)

        today = date.today()
        due_today = (
            db.query(InvestmentPlanExecution)
            .join(InvestmentPlan)
            .filter(
                InvestmentPlanExecution.executed == False,
                InvestmentPlanExecution.scheduled_date == today,
                InvestmentPlan.is_active == True,
            )
            .all()
        )
        if not due_today:
            return {"checked": 0, "due_today": [], "notified": False}

        items = []
        for e in due_today:
            plan = e.plan
            items.append({
                "fund_code": plan.fund_code,
                "plan_name": plan.plan_name or "",
                "amount": float(plan.amount or 0),
            })

        notified = False
        try:
            from backend.services.notification import send_investment_reminder
            send_investment_reminder(items)
            notified = True
        except Exception as exc:
            logger.warning(f"定投提醒推送失败: {exc}")

        return {"checked": len(due_today), "due_today": items, "notified": notified}
    finally:
        if own_db:
            db.close()


# ──────────────── helpers ────────────────

def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _plan_stats(db: Session, plan: InvestmentPlan) -> dict:
    """单计划的进度统计 — 用于列表展示"""
    executed_rows = (
        db.query(InvestmentPlanExecution)
        .filter(InvestmentPlanExecution.plan_id == plan.id,
                InvestmentPlanExecution.executed == True)
        .all()
    )
    cumulative_amount = sum(float(e.actual_amount or 0) for e in executed_rows)
    cumulative_shares = sum(float(e.actual_shares or 0) for e in executed_rows)
    average_cost = cumulative_amount / cumulative_shares if cumulative_shares else 0

    holding = (
        db.query(Holding)
        .filter(Holding.fund_code == plan.fund_code,
                Holding.is_active == True)
        .first()
    )
    latest_nav = float(holding.current_nav or 0) if holding else 0
    current_value = cumulative_shares * latest_nav
    pnl = current_value - cumulative_amount
    pnl_pct = (pnl / cumulative_amount * 100) if cumulative_amount > 0 else 0

    upcoming = (
        db.query(InvestmentPlanExecution)
        .filter(InvestmentPlanExecution.plan_id == plan.id,
                InvestmentPlanExecution.executed == False,
                InvestmentPlanExecution.scheduled_date >= date.today())
        .order_by(InvestmentPlanExecution.scheduled_date.asc())
        .first()
    )

    target_amount = float(plan.target_amount or 0)
    target_periods = int(target_amount / float(plan.amount)) if target_amount and plan.amount else 0

    return {
        "executed_periods": len(executed_rows),
        "target_periods": target_periods,
        "cumulative_amount": round(cumulative_amount, 2),
        "cumulative_shares": round(cumulative_shares, 4),
        "average_cost": round(average_cost, 4),
        "current_value": round(current_value, 2),
        "current_pnl": round(pnl, 2),
        "current_pnl_pct": round(pnl_pct, 2),
        "next_execution_date": upcoming.scheduled_date.isoformat() if upcoming else None,
    }
