"""
老基民小工具集 — P2.4

集中实现 5 个独立小工具，复用已有数据，零新建表：
1. holding_milestones        — 持有时长里程碑（7/30/365/730 天）+ 距离免赎回费节点天数
2. quarterly_disclosure      — 季报披露日历（4/8/10/次年 1 月底）+ 持仓基金披露状态
3. switch_savings            — 同公司基金转换费率计算（赎回费 + 申购费 vs 转换费节省）
4. holiday_alerts            — 节假日提醒（基于 market_holidays.json，长假前后操作建议）
5. fee_health_summary        — 全持仓费率体检：哪些基金即将跨过费率门槛、哪些处于高费率档

设计原则：
- 所有工具都基于现有 holdings / fund_fee_schedules / fund / market_holidays.json 计算
- 不引入新数据表，纯查询 + 算法
- 每个工具都返回 {items, summary, recommendations}
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from backend.config import BASE_DIR
from backend.models.fund import Fund
from backend.models.fund_fee import FundFeeSchedule
from backend.models.holding import Holding


# ──────────────── 1. 持有时长里程碑 ────────────────

MILESTONE_DAYS = [7, 30, 90, 180, 365, 730]  # 标准里程碑


def _f(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _load_redemption_schedule(fee: FundFeeSchedule | None) -> list[dict]:
    if not fee or not fee.redemption_fee_schedule:
        return []
    try:
        raw = json.loads(fee.redemption_fee_schedule)
    except Exception as e:
        logger.debug(f"赎回费档解析失败 {fee.fund_code}: {e}")
        return []
    if not isinstance(raw, list):
        return []
    return sorted(raw, key=lambda x: int(x.get("min_days", 0)))


def _redemption_rate_for_days(schedule: list[dict], holding_days: int) -> float:
    for row in schedule:
        min_days = int(row.get("min_days", 0))
        max_days = int(row.get("max_days", 999999))
        if min_days <= holding_days <= max_days:
            return _f(row.get("rate"))
    return 0.0


def _next_fee_drop(schedule: list[dict], holding_days: int, current_rate: float) -> tuple[float | None, int | None]:
    for row in schedule:
        min_days = int(row.get("min_days", 0))
        rate = _f(row.get("rate"))
        if min_days > holding_days and rate < current_rate:
            return rate, min_days - holding_days
    return None, None


def holding_milestones(db: Session) -> dict:
    """每只持仓的"距离下一个里程碑"和"距离下一个降费档"的天数"""
    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    if not holdings:
        return {"items": [], "summary": "暂无持仓", "imminent": []}

    fee_map = {
        r.fund_code: r for r in
        db.query(FundFeeSchedule)
        .filter(FundFeeSchedule.fund_code.in_([h.fund_code for h in holdings]))
        .all()
    }

    items = []
    imminent = []  # 近 7 天内会跨越里程碑或降费档
    today = date.today()
    for h in holdings:
        start = h.created_at.date() if h.created_at else today
        days = max(0, (today - start).days)

        # 下一个里程碑
        next_milestone = next((m for m in MILESTONE_DAYS if m > days), None)
        days_to_milestone = (next_milestone - days) if next_milestone else None

        # 下一个降费档
        next_fee_drop = None
        days_to_fee_drop = None
        current_rate = 0.0
        fee = fee_map.get(h.fund_code)
        schedule = _load_redemption_schedule(fee)
        if schedule:
            current_rate = _redemption_rate_for_days(schedule, days)
            next_fee_drop, days_to_fee_drop = _next_fee_drop(schedule, days, current_rate)

        # 近 7 天即将到达的事件
        is_imminent = (
            (days_to_milestone is not None and days_to_milestone <= 7)
            or (days_to_fee_drop is not None and days_to_fee_drop <= 7)
        )
        row = {
            "fund_code": h.fund_code,
            "fund_name": h.fund.fund_name if h.fund else "",
            "holding_days": days,
            "current_value": float(h.current_value or 0),
            "next_milestone": next_milestone,
            "days_to_milestone": days_to_milestone,
            "current_redemption_rate": current_rate,
            "next_fee_rate": next_fee_drop,
            "days_to_fee_drop": days_to_fee_drop,
            "savings_at_fee_drop": (
                round(float(h.current_value or 0) * max(current_rate - next_fee_drop, 0), 2)
                if next_fee_drop is not None else None
            ),
        }
        items.append(row)
        if is_imminent:
            imminent.append(row)

    items.sort(key=lambda x: (x["days_to_fee_drop"] is None, x["days_to_fee_drop"] or 99999))
    return {
        "items": items,
        "imminent": imminent,
        "summary": f"持仓 {len(items)} 只，近 7 天将跨越里程碑/降费档：{len(imminent)} 只",
    }


# ──────────────── 2. 季报披露日历 ────────────────

# 季报披露窗口：每个自然季度结束后 15-30 天
DISCLOSURE_WINDOWS = [
    {"quarter": "Q1", "start_md": (4, 21), "end_md": (4, 30)},
    {"quarter": "Q2", "start_md": (7, 21), "end_md": (7, 31)},   # 中报截止 8/31，前 10 大持仓 7 月末
    {"quarter": "Q3", "start_md": (10, 21), "end_md": (10, 31)},
    {"quarter": "Q4", "start_md": (1, 21), "end_md": (1, 31)},   # 次年 1 月末
]


def quarterly_disclosure(db: Session) -> dict:
    """返回最近一次披露窗口的状态 + 下一次披露窗口距今天数"""
    today = date.today()
    year = today.year

    # 生成最近 4 个披露窗口（含未来和过去各 2 个）
    windows = []
    for off_year in (year - 1, year, year + 1):
        for w in DISCLOSURE_WINDOWS:
            # Q4 数据在次年 1 月末披露
            disc_year = off_year + 1 if w["quarter"] == "Q4" else off_year
            window_start = date(disc_year, w["start_md"][0], w["start_md"][1])
            window_end = date(disc_year, w["end_md"][0], w["end_md"][1])
            windows.append({
                "quarter_label": f"{off_year}{w['quarter']}",
                "disclosure_start": window_start.isoformat(),
                "disclosure_end": window_end.isoformat(),
                "is_past": window_end < today,
                "is_current": window_start <= today <= window_end,
                "days_to_start": (window_start - today).days if window_start > today else 0,
                "days_to_end": (window_end - today).days if window_end >= today else 0,
            })

    # 当前 + 下一个 + 过去 1 个
    past = [w for w in windows if w["is_past"]]
    current = [w for w in windows if w["is_current"]]
    upcoming = [w for w in windows if not w["is_past"] and not w["is_current"]]
    next_window = min(upcoming, key=lambda w: w["days_to_start"]) if upcoming else None
    last_window = max(past, key=lambda w: w["disclosure_end"]) if past else None

    # 持仓基金的披露完整度（最近一次披露：检查 fund_top_holdings 是否有该季度数据）
    from backend.models.fund_top_holding import FundTopHolding
    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    fund_status = []
    if holdings and last_window:
        # 取最近一次完整披露的季度
        last_quarter = last_window["quarter_label"]
        rows = (
            db.query(FundTopHolding.fund_code, FundTopHolding.quarter)
            .filter(FundTopHolding.fund_code.in_([h.fund_code for h in holdings]),
                    FundTopHolding.quarter == last_quarter)
            .distinct()
            .all()
        )
        covered = {r[0] for r in rows}
        for h in holdings:
            fund_status.append({
                "fund_code": h.fund_code,
                "fund_name": h.fund.fund_name if h.fund else "",
                "last_quarter": last_quarter,
                "has_data": h.fund_code in covered,
            })

    return {
        "current_window": current[0] if current else None,
        "next_window": next_window,
        "last_window": last_window,
        "fund_disclosure_status": fund_status,
        "summary": (
            f"距下次季报披露还有 {next_window['days_to_start']} 天（{next_window['quarter_label']}）"
            if next_window else "本季度披露窗口已开启"
        ),
    }


# ──────────────── 3. 同公司基金转换费率计算 ────────────────

def switch_savings(db: Session, from_code: str, to_code: str,
                   amount: float | None = None,
                   convert_fee_rate: float = 0.005) -> dict:
    """对比"直接赎回 + 申购" vs "转换" 的费用节省

    convert_fee_rate: 同公司转换费率（默认 0.5%，实际依基金公司）
    """
    from_holding = (
        db.query(Holding).options(joinedload(Holding.fund))
        .filter(Holding.fund_code == from_code, Holding.is_active == True)
        .first()
    )
    if not from_holding:
        return {"error": f"未持有基金 {from_code}"}

    from_fee = db.query(FundFeeSchedule).filter(FundFeeSchedule.fund_code == from_code).first()
    to_fee = db.query(FundFeeSchedule).filter(FundFeeSchedule.fund_code == to_code).first()

    amount = amount or float(from_holding.current_value or 0)
    if amount <= 0:
        return {"error": "金额需大于 0"}

    # 直接赎回手续费
    holding_days = (date.today() - (from_holding.created_at.date() if from_holding.created_at else date.today())).days
    redemption_rate = _redemption_rate_for_days(_load_redemption_schedule(from_fee), holding_days)
    redemption_fee = amount * redemption_rate

    # 申购费 = 申购费率 × 折扣
    purchase_rate = float(to_fee.purchase_fee_rate or 0) if to_fee else 0
    discount = float(to_fee.purchase_fee_discount or 0.1) if to_fee else 0.1
    effective_purchase_rate = purchase_rate * discount
    # 申购费按"净申购金额"，但简化按总额近似
    purchase_fee = amount * effective_purchase_rate

    # 直接走两步的总费用
    direct_total_fee = redemption_fee + purchase_fee

    # 转换费用
    convert_fee = amount * convert_fee_rate

    # 节省
    savings = direct_total_fee - convert_fee

    from_fund = from_holding.fund
    to_fund = db.query(Fund).filter(Fund.fund_code == to_code).first()
    same_company = bool(
        from_fund and to_fund
        and from_fund.company
        and to_fund.company
        and from_fund.company == to_fund.company
    )
    company_warning = ""
    if from_fund and to_fund and from_fund.company and to_fund.company and not same_company:
        company_warning = f"两只基金公司不同（{from_fund.company} / {to_fund.company}），通常不支持同公司基金转换"

    return {
        "from": {
            "code": from_code,
            "name": from_fund.fund_name if from_fund else "",
            "company": from_fund.company if from_fund else "",
            "holding_days": holding_days,
            "redemption_rate": redemption_rate,
            "redemption_fee": round(redemption_fee, 2),
        },
        "to": {
            "code": to_code,
            "name": to_fund.fund_name if to_fund else "",
            "company": to_fund.company if to_fund else "",
            "purchase_rate": purchase_rate,
            "discount": discount,
            "effective_purchase_rate": round(effective_purchase_rate, 5),
            "purchase_fee": round(purchase_fee, 2),
        },
        "direct_total_fee": round(direct_total_fee, 2),
        "convert_fee_rate": convert_fee_rate,
        "convert_fee": round(convert_fee, 2),
        "savings": round(savings, 2),
        "amount": round(amount, 2),
        "same_company": same_company,
        "company_warning": company_warning,
        "recommendation": (
            company_warning if company_warning else
            f"建议使用同公司转换功能 — 可节省 ¥{savings:.2f}（{savings/amount*100:.3f}%）"
            if savings > 0 else
            f"直接赎回再申购更划算（转换反而多花 ¥{-savings:.2f}）"
        ),
    }


# ──────────────── 4. 节假日提醒 ────────────────

def holiday_alerts() -> dict:
    """读取 market_holidays.json，输出未来 30 天的节假日 + 长假前/后操作建议"""
    today = date.today()
    horizon = today + timedelta(days=30)

    path = Path(BASE_DIR) / "data" / "market_holidays.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        holidays = raw.get("holidays", [])
    except Exception as e:
        logger.warning(f"读取交易日历失败: {e}")
        return {"items": [], "summary": "无法读取交易日历", "error": str(e)}

    # 解析为 date 对象 + 排序
    parsed = []
    for d in holidays:
        try:
            parsed.append(date.fromisoformat(d))
        except ValueError:
            continue
    parsed.sort()

    # 识别连续假期块。market_holidays.json 只列工作日休市日期，
    # 需要把夹在中间的周末也归入同一长假窗口。
    blocks = []
    if parsed:
        current_block = [parsed[0]]
        for d in parsed[1:]:
            if _is_same_holiday_block(current_block[-1], d):
                current_block.append(d)
            else:
                blocks.append(current_block)
                current_block = [d]
        blocks.append(current_block)

    # 取未来 30 天内的假期块
    upcoming = []
    for block in blocks:
        block_start = block[0]
        block_end = block[-1]
        if block_end < today:
            continue
        if block_start > horizon:
            break
        days_to_start = (block_start - today).days
        length = (block_end - block_start).days + 1
        upcoming.append({
            "start": block_start.isoformat(),
            "end": block_end.isoformat(),
            "length": length,
            "days_to_start": max(days_to_start, 0),
            "is_long": length >= 3,
            "is_imminent": 0 <= days_to_start <= 3,
            "advice": _holiday_advice(length, days_to_start),
        })

    summary = "近 30 天无重要假期"
    long_holidays = [b for b in upcoming if b["is_long"]]
    if long_holidays:
        nearest = min(long_holidays, key=lambda b: b["days_to_start"])
        summary = f"距下个长假（{nearest['length']} 天）还有 {nearest['days_to_start']} 天"

    return {
        "items": upcoming,
        "summary": summary,
        "long_holiday_count": len(long_holidays),
    }


def _is_same_holiday_block(prev_day: date, next_day: date) -> bool:
    gap = (next_day - prev_day).days
    if gap == 1:
        return True
    if gap <= 1 or gap > 4:
        return False
    return all((prev_day + timedelta(days=i)).weekday() >= 5 for i in range(1, gap))


def _holiday_advice(length: int, days_to_start: int) -> str:
    if length >= 5:
        if 0 <= days_to_start <= 2:
            return "⚠️ 长假即将到来 — 假期内 T+1 资金到账延迟，谨慎调仓"
        if 3 <= days_to_start <= 7:
            return "考虑长假前减少股票型仓位（历史上长假前后波动加大）"
    if length == 3 and 0 <= days_to_start <= 1:
        return "小长假 — 注意 T+1 申购确认时点"
    return ""


# ──────────────── 5. 全持仓费率体检 ────────────────

def fee_health_summary(db: Session) -> dict:
    """快速扫描所有持仓的费率健康度"""
    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    if not holdings:
        return {"items": [], "summary": "暂无持仓"}

    fee_map = {
        r.fund_code: r for r in
        db.query(FundFeeSchedule)
        .filter(FundFeeSchedule.fund_code.in_([h.fund_code for h in holdings]))
        .all()
    }

    items = []
    no_fee_data = []
    high_fee = []
    for h in holdings:
        fee = fee_map.get(h.fund_code)
        if not fee:
            no_fee_data.append(h.fund_code)
            continue

        annual_rate = (
            float(fee.management_fee_rate or 0)
            + float(fee.custody_fee_rate or 0)
            + float(fee.sales_service_fee_rate or 0)
        )
        value = float(h.current_value or 0)
        annual_cost = value * annual_rate
        items.append({
            "fund_code": h.fund_code,
            "fund_name": h.fund.fund_name if h.fund else "",
            "current_value": round(value, 2),
            "annual_rate_pct": round(annual_rate * 100, 3),
            "annual_cost": round(annual_cost, 2),
            "is_high_fee": annual_rate >= 0.02,  # 综合 2% 算高费率
        })
        if annual_rate >= 0.02:
            high_fee.append(h.fund_code)

    items.sort(key=lambda x: x["annual_cost"], reverse=True)
    total_annual_cost = sum(it["annual_cost"] for it in items)
    avg_rate = (
        sum(it["annual_rate_pct"] * it["current_value"] for it in items)
        / sum(it["current_value"] for it in items)
    ) if items else 0

    return {
        "items": items,
        "total_annual_cost": round(total_annual_cost, 2),
        "avg_rate_pct": round(avg_rate, 3),
        "high_fee_funds": high_fee,
        "missing_fee_data": no_fee_data,
        "summary": (
            f"年化总费用约 ¥{total_annual_cost:.2f}，加权年费率 {avg_rate:.3f}%；"
            f"高费率基金 {len(high_fee)} 只，缺费率配置 {len(no_fee_data)} 只"
        ),
    }


# ──────────────── 每日里程碑提醒 ────────────────

def daily_milestone_check(db: Session | None = None) -> dict:
    """每个交易日 9:30 跑：扫描所有持仓，对近 3 天会跨费率档的发飞书提醒"""
    own = db is None
    from backend.database import SessionLocal
    db = db or SessionLocal()
    try:
        result = holding_milestones(db)
        urgent = [
            x for x in result.get("imminent", [])
            if x.get("days_to_fee_drop") is not None
            and x["days_to_fee_drop"] <= 3
            and x["days_to_fee_drop"] >= 0
            and (x.get("savings_at_fee_drop") or 0) > 50  # 节省金额 > ¥50 才推
        ]
        if urgent:
            try:
                from backend.services.notification import send_milestone_alert
                send_milestone_alert(urgent)
            except Exception as e:
                logger.warning(f"里程碑飞书推送失败: {e}")
        return {"checked": len(result.get("items", [])), "urgent": urgent}
    finally:
        if own:
            db.close()
