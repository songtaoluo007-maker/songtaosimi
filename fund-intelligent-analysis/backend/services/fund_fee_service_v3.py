"""
基金费率账本服务 — P2.1

三大能力：
1. CRUD 费率表（手动维护 / 未来扩展自动采集）
2. 每日费率计提（持仓市值 × 年费率 / 365） — APScheduler 每日 21:00 跑
3. 赎回费预估（用户卖出前必看）+ 年度账本统计
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from loguru import logger
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.fund import Fund
from backend.models.fund_fee import FeeDailyAccrual, FundFeeSchedule
from backend.models.holding import Holding


# ──────────────── 费率 CRUD ────────────────

def list_fee_schedules(db: Session) -> list[dict]:
    rows = db.query(FundFeeSchedule).order_by(FundFeeSchedule.fund_code.asc()).all()
    fund_names = {f.fund_code: f.fund_name for f in db.query(Fund).all()}
    return [{**r.to_dict(), "fund_name": fund_names.get(r.fund_code, "")} for r in rows]


def get_fee_schedule(db: Session, fund_code: str) -> dict | None:
    row = db.query(FundFeeSchedule).filter(FundFeeSchedule.fund_code == fund_code).first()
    return row.to_dict() if row else None


def upsert_fee_schedule(db: Session, fund_code: str, payload: dict) -> dict:
    row = db.query(FundFeeSchedule).filter(FundFeeSchedule.fund_code == fund_code).first()
    if not row:
        row = FundFeeSchedule(fund_code=fund_code)
        db.add(row)

    if "purchase_fee_rate" in payload:
        row.purchase_fee_rate = float(payload["purchase_fee_rate"] or 0)
    if "purchase_fee_discount" in payload:
        row.purchase_fee_discount = float(payload["purchase_fee_discount"] or 0.1)
    if "redemption_fee_schedule" in payload:
        sched = payload["redemption_fee_schedule"]
        # 接受 list 或字符串，统一存为 JSON 字符串
        row.redemption_fee_schedule = (
            json.dumps(sched, ensure_ascii=False)
            if isinstance(sched, (list, dict))
            else str(sched or "")
        )
    if "management_fee_rate" in payload:
        row.management_fee_rate = float(payload["management_fee_rate"] or 0)
    if "custody_fee_rate" in payload:
        row.custody_fee_rate = float(payload["custody_fee_rate"] or 0)
    if "sales_service_fee_rate" in payload:
        row.sales_service_fee_rate = float(payload["sales_service_fee_rate"] or 0)
    if "source" in payload:
        row.source = payload["source"]

    db.commit()
    db.refresh(row)
    return row.to_dict()


# ──────────────── 每日计提 ────────────────

def daily_fee_accrual(db: Session | None = None, target_day: date | None = None) -> dict:
    """按持仓市值 × 年费率/365 计提日费用；同一天同基金幂等"""
    own = db is None
    db = db or SessionLocal()
    try:
        target_day = target_day or date.today()
        holdings = (
            db.query(Holding).filter(Holding.is_active == True).all()
        )
        if not holdings:
            return {"accrual_date": target_day.isoformat(), "items": [],
                    "message": "无活跃持仓"}

        existing = {
            (r.fund_code, r.accrual_date): r for r in
            db.query(FeeDailyAccrual).filter(FeeDailyAccrual.accrual_date == target_day).all()
        }
        fee_map = {
            r.fund_code: r for r in
            db.query(FundFeeSchedule).filter(
                FundFeeSchedule.fund_code.in_([h.fund_code for h in holdings])
            ).all()
        }

        inserted = updated = skipped = 0
        items: list[dict] = []
        for h in holdings:
            fee = fee_map.get(h.fund_code)
            if not fee:
                skipped += 1
                continue
            value = float(h.current_value or 0)
            if value <= 0:
                skipped += 1
                continue
            mgmt = value * float(fee.management_fee_rate or 0) / 365
            custody = value * float(fee.custody_fee_rate or 0) / 365
            sales = value * float(fee.sales_service_fee_rate or 0) / 365

            row = existing.get((h.fund_code, target_day))
            if row:
                row.holding_value = round(value, 2)
                row.daily_mgmt_fee = round(mgmt, 4)
                row.daily_custody_fee = round(custody, 4)
                row.daily_sales_fee = round(sales, 4)
                updated += 1
            else:
                row = FeeDailyAccrual(
                    accrual_date=target_day,
                    fund_code=h.fund_code,
                    holding_value=round(value, 2),
                    daily_mgmt_fee=round(mgmt, 4),
                    daily_custody_fee=round(custody, 4),
                    daily_sales_fee=round(sales, 4),
                )
                db.add(row)
                inserted += 1
            items.append({
                "fund_code": h.fund_code,
                "holding_value": round(value, 2),
                "daily_total": round(mgmt + custody + sales, 4),
            })
        db.commit()
        logger.info(
            f"费率计提完成 {target_day}: 新增 {inserted} / 更新 {updated} / 跳过 {skipped}"
        )
        return {
            "accrual_date": target_day.isoformat(),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "items": items,
        }
    finally:
        if own:
            db.close()


# ──────────────── 年度账本统计 ────────────────

def yearly_ledger(db: Session, year: int | None = None) -> dict:
    """返回 {year, total_value_avg, total_fee_year, by_fund: [...], by_month: [...]} """
    today = date.today()
    year = year or today.year
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    rows = (
        db.query(FeeDailyAccrual)
        .filter(
            FeeDailyAccrual.accrual_date >= start,
            FeeDailyAccrual.accrual_date <= end,
        )
        .all()
    )
    if not rows:
        return {"year": year, "total_fee": 0, "by_fund": [], "by_month": [],
                "message": "本年度尚无费率计提数据"}

    fund_names = {f.fund_code: f.fund_name for f in db.query(Fund).all()}

    # 按基金汇总
    by_fund_dict: dict[str, dict] = {}
    by_month_dict: dict[str, dict] = {}
    total_fee = 0.0
    for r in rows:
        fee_total = r.daily_total_fee
        total_fee += fee_total

        # 按基金
        if r.fund_code not in by_fund_dict:
            by_fund_dict[r.fund_code] = {
                "fund_code": r.fund_code,
                "fund_name": fund_names.get(r.fund_code, ""),
                "mgmt_fee": 0.0,
                "custody_fee": 0.0,
                "sales_fee": 0.0,
                "total_fee": 0.0,
                "days": 0,
                "avg_holding_value": 0.0,
            }
        bf = by_fund_dict[r.fund_code]
        bf["mgmt_fee"] += float(r.daily_mgmt_fee or 0)
        bf["custody_fee"] += float(r.daily_custody_fee or 0)
        bf["sales_fee"] += float(r.daily_sales_fee or 0)
        bf["total_fee"] += fee_total
        bf["days"] += 1
        bf["avg_holding_value"] += float(r.holding_value or 0)

        # 按月
        month_key = r.accrual_date.strftime("%Y-%m")
        if month_key not in by_month_dict:
            by_month_dict[month_key] = {"month": month_key, "total_fee": 0.0}
        by_month_dict[month_key]["total_fee"] += fee_total

    # 平均持仓
    for bf in by_fund_dict.values():
        if bf["days"]:
            bf["avg_holding_value"] = round(bf["avg_holding_value"] / bf["days"], 2)
        for k in ("mgmt_fee", "custody_fee", "sales_fee", "total_fee"):
            bf[k] = round(bf[k], 2)

    by_fund = sorted(by_fund_dict.values(), key=lambda x: x["total_fee"], reverse=True)
    by_month = sorted(by_month_dict.values(), key=lambda x: x["month"])
    for m in by_month:
        m["total_fee"] = round(m["total_fee"], 2)

    # 计算费率拖累：累计费 / 平均组合市值 → 年化拖累
    avg_total_value = sum(bf["avg_holding_value"] for bf in by_fund_dict.values())
    drag_pct = (total_fee / avg_total_value * 100) if avg_total_value > 0 else 0

    return {
        "year": year,
        "total_fee": round(total_fee, 2),
        "avg_total_value": round(avg_total_value, 2),
        "drag_pct": round(drag_pct, 3),
        "by_fund": by_fund,
        "by_month": by_month,
    }


# ──────────────── 赎回费预估 ────────────────

def estimate_redemption_fee(db: Session, fund_code: str,
                            redeem_shares: float | None = None,
                            redeem_amount: float | None = None) -> dict:
    holding = (
        db.query(Holding)
        .filter(Holding.fund_code == fund_code, Holding.is_active == True)
        .first()
    )
    if not holding:
        return {"error": "未持有该基金"}

    fee = db.query(FundFeeSchedule).filter(FundFeeSchedule.fund_code == fund_code).first()
    schedule = []
    if fee and fee.redemption_fee_schedule:
        try:
            schedule = json.loads(fee.redemption_fee_schedule)
        except Exception:
            schedule = []

    # 持有天数：从 holdings.created_at 算起
    start_dt = holding.created_at.date() if holding.created_at else date.today()
    holding_days = (date.today() - start_dt).days

    # 找到匹配的费率档
    matched_rate = 0.0
    matched_window = None
    for s in schedule:
        min_d = int(s.get("min_days", 0))
        max_d = int(s.get("max_days", 99999))
        if min_d <= holding_days <= max_d:
            matched_rate = float(s.get("rate") or 0)
            matched_window = f"{min_d}-{max_d if max_d < 99999 else '∞'} 天"
            break

    nav = float(holding.current_nav or 0)
    if redeem_amount is None and redeem_shares is not None:
        redeem_amount = redeem_shares * nav
    if redeem_shares is None and redeem_amount is not None and nav > 0:
        redeem_shares = redeem_amount / nav
    redeem_amount = redeem_amount or float(holding.current_value or 0)
    redeem_shares = redeem_shares or float(holding.shares or 0)

    fee_amount = redeem_amount * matched_rate
    net_amount = redeem_amount - fee_amount

    # 下一个免费/降费档的剩余天数
    next_window = None
    for s in schedule:
        min_d = int(s.get("min_days", 0))
        if min_d > holding_days and float(s.get("rate") or 0) < matched_rate:
            next_window = {
                "after_days": min_d - holding_days,
                "rate": float(s.get("rate") or 0),
                "savings_at_current_amount": round(redeem_amount * (matched_rate - float(s.get("rate") or 0)), 2),
            }
            break

    return {
        "fund_code": fund_code,
        "holding_days": holding_days,
        "matched_rate": matched_rate,
        "matched_rate_pct": round(matched_rate * 100, 3),
        "matched_window": matched_window,
        "redeem_shares": round(redeem_shares, 4),
        "redeem_amount": round(redeem_amount, 2),
        "fee_amount": round(fee_amount, 2),
        "net_amount": round(net_amount, 2),
        "next_window": next_window,
        "warning": _build_redemption_warning(holding_days, matched_rate, next_window),
    }


def _build_redemption_warning(days: int, rate: float, next_window: dict | None) -> str:
    parts: list[str] = []
    if rate >= 0.015:
        parts.append(f"⚠️ 当前持有仅 {days} 天，赎回费率 {rate*100:.2f}% 偏高")
    if next_window:
        parts.append(
            f"再持有 {next_window['after_days']} 天可降至 {next_window['rate']*100:.2f}%，"
            f"按当前金额可节省 ¥{next_window['savings_at_current_amount']:.2f}"
        )
    if not parts:
        if rate == 0:
            return "已过免赎回费门槛"
        return f"持有 {days} 天，赎回费率 {rate*100:.2f}%"
    return "；".join(parts)
