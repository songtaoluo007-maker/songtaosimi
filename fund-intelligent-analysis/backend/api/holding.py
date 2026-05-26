from datetime import date, datetime, timedelta
from calendar import monthrange

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from backend.database import get_db
from backend.models.holding import Holding
from backend.models.fund import Fund
from backend.schemas.holding import HoldingCreate, HoldingUpdate, HoldingResponse, HoldingSummary
from backend.services.fund_nav_collector import fetch_fund_info, fetch_latest_nav
from backend.utils import to_float as _float


def _date_range(start: date, end: date) -> list[date]:
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _resolve_period_range(period: str, anchor: date, db: Session) -> tuple[date, date, str]:
    period = (period or "month").lower()
    if period == "day":
        return anchor, anchor, "当日"
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6), "当周"
    if period == "year":
        return date(anchor.year, 1, 1), date(anchor.year, 12, 31), "当年"
    if period == "inception":
        starts = []
        first_holding = db.query(Holding).filter(Holding.is_active == True).order_by(Holding.created_at.asc()).first()
        if first_holding and first_holding.created_at:
            starts.append(first_holding.created_at.date())
        from backend.models.trade import Trade
        from backend.models.market_snapshot import MarketSnapshot

        first_trade = db.query(Trade).order_by(Trade.trade_date.asc()).first()
        if first_trade and first_trade.trade_date:
            starts.append(first_trade.trade_date)
        first_snapshot = db.query(MarketSnapshot).filter(
            MarketSnapshot.snapshot_type == "fund",
        ).order_by(MarketSnapshot.snapshot_date.asc()).first()
        if first_snapshot and first_snapshot.snapshot_date:
            starts.append(first_snapshot.snapshot_date)
        start = min(starts) if starts else date(anchor.year, 1, 1)
        return start, anchor, "开户以来"
    last_day = monthrange(anchor.year, anchor.month)[1]
    return date(anchor.year, anchor.month, 1), date(anchor.year, anchor.month, last_day), "当月"


def _snapshot_maps(db: Session, fund_codes: list[str], start: date, end: date):
    from backend.models.market_snapshot import MarketSnapshot

    symbols = [f"fund_{code}" for code in fund_codes]
    if not symbols:
        return {}, {}
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == "fund",
        MarketSnapshot.symbol.in_(symbols),
        MarketSnapshot.snapshot_date >= start - timedelta(days=10),
        MarketSnapshot.snapshot_date <= end,
    ).order_by(MarketSnapshot.symbol.asc(), MarketSnapshot.snapshot_date.asc(), MarketSnapshot.snapshot_time.asc()).all()

    latest_by_day = {}
    by_symbol_dates: dict[str, list[tuple[date, MarketSnapshot]]] = {}
    for snap in snapshots:
        code = str(snap.symbol).replace("fund_", "")
        latest_by_day[(code, snap.snapshot_date)] = snap
        by_symbol_dates.setdefault(code, [])
        if not by_symbol_dates[code] or by_symbol_dates[code][-1][0] != snap.snapshot_date:
            by_symbol_dates[code].append((snap.snapshot_date, snap))
        else:
            by_symbol_dates[code][-1] = (snap.snapshot_date, snap)
    return latest_by_day, by_symbol_dates


def _latest_before(by_symbol_dates: dict, code: str, target: date, include_target: bool = True):
    selected = None
    for row_date, snap in by_symbol_dates.get(code, []):
        if row_date < target or (include_target and row_date == target):
            selected = snap
        if row_date > target:
            break
    return selected


def _benchmark_daily_map(db: Session, start: date, end: date):
    from backend.models.market_snapshot import MarketSnapshot

    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == "000300.SH",
        MarketSnapshot.snapshot_type == "index",
        MarketSnapshot.snapshot_date >= start - timedelta(days=10),
        MarketSnapshot.snapshot_date <= end,
    ).order_by(MarketSnapshot.snapshot_date.asc(), MarketSnapshot.snapshot_time.asc()).all()
    by_day = {}
    for snap in snapshots:
        by_day[snap.snapshot_date] = snap
    rows = sorted(by_day.items(), key=lambda item: item[0])

    def before(target: date, include_target: bool = True):
        selected = None
        for row_date, snap in rows:
            if row_date < target or (include_target and row_date == target):
                selected = snap
            if row_date > target:
                break
        return selected

    result = {}
    for day in _date_range(start, end):
        current = before(day, True)
        prev = before(day, False)
        if current and prev and _float(prev.price) > 0:
            result[day] = (_float(current.price) - _float(prev.price)) / _float(prev.price) * 100
        elif current:
            result[day] = _float(current.change_pct)
    return result, before

router = APIRouter(prefix="/api/holdings", tags=["持仓管理"])


@router.get("")
def list_holdings(is_active: Optional[bool] = True, db: Session = Depends(get_db)):
    """获取当前持仓列表"""
    query = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == is_active)
    holdings = query.all()
    result = []
    for h in holdings:
        d = h.to_dict()
        result.append(d)
    return result


@router.get("/summary")
def get_holdings_summary(db: Session = Depends(get_db)):
    """持仓汇总统计"""
    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()

    total_value = sum(float(h.current_value or 0) for h in holdings)
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_ratio = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    total_daily_pnl = sum(float(h.daily_pnl or 0) for h in holdings)
    daily_dates = [h.daily_pnl_date for h in holdings if h.daily_pnl_date]
    daily_pnl_date = max(daily_dates).isoformat() if daily_dates else ""

    # 按基金类型分布
    allocation = {}
    for h in holdings:
        fund_type = h.fund.fund_type if h.fund else "未知"
        val = float(h.current_value or 0)
        allocation[fund_type] = allocation.get(fund_type, 0) + val

    alloc_list = [
        {"type": k, "value": v, "ratio": round(v / total_value * 100, 2) if total_value > 0 else 0}
        for k, v in allocation.items()
    ]

    return HoldingSummary(
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_ratio=round(total_pnl_ratio, 2),
        total_daily_pnl=round(total_daily_pnl, 2),
        daily_pnl_date=daily_pnl_date,
        holding_count=len(holdings),
        allocation=alloc_list,
    )


@router.post("/refresh-estimates")
def refresh_holding_estimates(db: Session = Depends(get_db)):
    """立即刷新持仓基金实时估值"""
    from backend.services.fund_nav_collector import collect_fund_estimates
    collect_fund_estimates()
    db.expire_all()
    return get_holdings_summary(db)


@router.get("/performance")
def get_holding_performance(db: Session = Depends(get_db)):
    """区间收益和沪深300对比（基于当前成本/市值与本地行情快照近似计算）"""
    from datetime import date, datetime, timedelta
    from backend.models.market_snapshot import MarketSnapshot

    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
    total_value = sum(float(h.current_value or 0) for h in holdings)
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)
    total_pnl = total_value - total_cost
    since_inception = total_pnl / total_cost * 100 if total_cost else 0

    today = date.today()
    latest_hs300 = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == "000300.SH",
        MarketSnapshot.snapshot_type == "index",
    ).order_by(MarketSnapshot.snapshot_date.desc(), MarketSnapshot.snapshot_time.desc()).first()

    hs300_today = float(latest_hs300.change_pct or 0) if latest_hs300 else 0
    periods = {
        "today": {"label": "当日", "days": 1},
        "week": {"label": "当周", "days": 7},
        "month": {"label": "当月", "days": 30},
        "year": {"label": "当年", "days": 365},
        "inception": {"label": "开户以来", "days": None},
    }
    rows = []
    for key, meta in periods.items():
        portfolio_return = since_inception
        benchmark_return = hs300_today
        if meta["days"]:
            start = today - timedelta(days=meta["days"])
            fund_snaps = db.query(MarketSnapshot).filter(
                MarketSnapshot.snapshot_type == "fund",
                MarketSnapshot.snapshot_date >= start,
            ).all()
            if fund_snaps:
                # 用快照估值变化做近似，数据不足时回落到总盈亏比例
                by_symbol = {}
                for s in sorted(fund_snaps, key=lambda x: (x.symbol, x.snapshot_date, x.snapshot_time)):
                    by_symbol.setdefault(s.symbol, []).append(float(s.price or 0))
                # 按持仓市值加权的组合收益率
                changes = []
                change_map = {}  # fund_code -> return%
                for symbol, vals in by_symbol.items():
                    fund_code = symbol.replace("fund_", "")
                    if len(vals) >= 2 and vals[0]:
                        change_map[fund_code] = (vals[-1] - vals[0]) / vals[0] * 100
                if change_map:
                    total_value = sum(float(h.current_value or 0) for h in holdings if h.fund_code in change_map)
                    if total_value > 0:
                        portfolio_return = sum(
                            change_map.get(h.fund_code, 0) * float(h.current_value or 0) / total_value
                            for h in holdings
                        )
                    else:
                        portfolio_return = sum(change_map.values()) / len(change_map)
            idx_start = db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == "000300.SH",
                MarketSnapshot.snapshot_date >= start,
            ).order_by(MarketSnapshot.snapshot_date.asc(), MarketSnapshot.snapshot_time.asc()).first()
            if idx_start and latest_hs300 and float(idx_start.price or 0):
                benchmark_return = (float(latest_hs300.price or 0) - float(idx_start.price or 0)) / float(idx_start.price) * 100
        rows.append({
            "period": key,
            "label": meta["label"],
            "portfolio_return": round(portfolio_return, 2),
            "hs300_return": round(benchmark_return, 2),
            "excess_return": round(portfolio_return - benchmark_return, 2),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return rows


@router.get("/performance-calendar")
def get_holding_performance_calendar(
    period: str = Query("month", pattern="^(day|week|month|year|inception)$"),
    target_date: Optional[date] = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    """收益日历：按日沉淀组合盈亏、贡献基金和沪深300对比。

    口径说明：优先使用本地基金实时估值快照计算日收益；没有快照的日期保留空值，
    当前日会回退到 holdings.daily_pnl，避免休市或上游接口失败时页面完全空白。
    """
    anchor = target_date or date.today()
    start, end, label = _resolve_period_range(period, anchor, db)
    today = date.today()
    if end > today:
        end = today
    if start > end:
        start = end

    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
    fund_codes = [h.fund_code for h in holdings]
    latest_by_day, by_symbol_dates = _snapshot_maps(db, fund_codes, start, end)
    benchmark_daily, benchmark_before = _benchmark_daily_map(db, start, end)

    days = []
    all_contributions = {}
    for day in _date_range(start, end):
        contributions = []
        total_value = 0.0
        daily_pnl = 0.0
        has_market_data = False

        for h in holdings:
            code = h.fund_code
            shares = _float(h.shares)
            snap = latest_by_day.get((code, day))
            prev = _latest_before(by_symbol_dates, code, day, include_target=False)
            price = _float(snap.price) if snap else None
            pnl = None
            return_pct = None

            if snap:
                has_market_data = True
                total_value += shares * _float(snap.price)
            if snap and prev and _float(prev.price) > 0:
                pnl = shares * (_float(snap.price) - _float(prev.price))
                return_pct = (_float(snap.price) - _float(prev.price)) / _float(prev.price) * 100
            elif h.daily_pnl_date == day:
                pnl = _float(h.daily_pnl)
                return_pct = _float(h.daily_pnl_ratio)
                price = _float(h.current_nav)
                total_value += _float(h.current_value)
                has_market_data = True

            if pnl is not None:
                daily_pnl += pnl
                contributions.append({
                    "fund_code": code,
                    "fund_name": h.fund.fund_name if h.fund else "",
                    "daily_pnl": round(pnl, 2),
                    "daily_return": round(return_pct or 0, 2),
                    "price": round(price or 0, 4),
                    "weight": round((_float(h.current_value) / sum(_float(x.current_value) for x in holdings) * 100) if holdings and sum(_float(x.current_value) for x in holdings) else 0, 2),
                })

        base_value = total_value - daily_pnl
        daily_return = daily_pnl / base_value * 100 if base_value > 0 else 0
        benchmark_return = benchmark_daily.get(day)
        day_status = "trading" if has_market_data else ("rest" if day.weekday() >= 5 else "no_data")
        contributions.sort(key=lambda item: item["daily_pnl"], reverse=True)
        row = {
            "date": day.isoformat(),
            "weekday": day.weekday(),
            "status": day_status,
            "daily_pnl": round(daily_pnl, 2) if has_market_data else None,
            "daily_return": round(daily_return, 2) if has_market_data else None,
            "benchmark_return": round(benchmark_return, 2) if benchmark_return is not None else None,
            "excess_return": round(daily_return - benchmark_return, 2) if has_market_data and benchmark_return is not None else None,
            "total_value": round(total_value, 2) if total_value else None,
            "top_gain": contributions[0] if contributions else None,
            "top_loss": contributions[-1] if contributions else None,
        }
        days.append(row)
        all_contributions[day.isoformat()] = contributions

    active_days = [d for d in days if d["daily_pnl"] is not None]
    total_pnl = sum(_float(d["daily_pnl"]) for d in active_days)
    win_days = len([d for d in active_days if _float(d["daily_pnl"]) > 0])
    loss_days = len([d for d in active_days if _float(d["daily_pnl"]) < 0])
    current_total_value = sum(_float(h.current_value) for h in holdings)
    cost_base = current_total_value - total_pnl
    period_return = total_pnl / cost_base * 100 if cost_base > 0 else 0

    start_bench = benchmark_before(start, True)
    end_bench = benchmark_before(end, True)
    benchmark_period_return = 0.0
    if start_bench and end_bench and _float(start_bench.price) > 0:
        benchmark_period_return = (_float(end_bench.price) - _float(start_bench.price)) / _float(start_bench.price) * 100

    selected_key = anchor.isoformat()
    if selected_key not in all_contributions and active_days:
        selected_key = active_days[-1]["date"]
    selected_day = next((d for d in days if d["date"] == selected_key), None)
    selected_contributions = all_contributions.get(selected_key, [])
    selected_contributions.sort(key=lambda item: item["daily_pnl"], reverse=True)

    return {
        "period": period,
        "label": label,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "selected_date": selected_key,
        "summary": {
            "total_pnl": round(total_pnl, 2),
            "period_return": round(period_return, 2),
            "benchmark_return": round(benchmark_period_return, 2),
            "excess_return": round(period_return - benchmark_period_return, 2),
            "win_days": win_days,
            "loss_days": loss_days,
            "active_days": len(active_days),
            "max_daily_gain": max((_float(d["daily_pnl"]) for d in active_days), default=0),
            "max_daily_loss": min((_float(d["daily_pnl"]) for d in active_days), default=0),
            "win_rate": round(win_days / len(active_days) * 100, 2) if active_days else 0,
        },
        "days": days,
        "selected_day": selected_day,
        "selected_contributions": selected_contributions,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_note": "优先使用本地实时估值快照；缺失日期显示为空，当前日可回退到持仓当日盈亏。",
    }


@router.post("")
def create_holding(data: HoldingCreate, db: Session = Depends(get_db)):
    """添加持仓"""
    # 确保基金存在，不存在则联网查询并自动创建
    fund = db.query(Fund).filter(Fund.fund_code == data.fund_code).first()
    if not fund:
        # 联网查询基金信息
        info = fetch_fund_info(data.fund_code)
        if not info.get("fund_name"):
            raise HTTPException(status_code=404, detail="未找到该基金，请确认基金代码是否正确")

        # 获取最新净值
        nav = fetch_latest_nav(data.fund_code)

        # 自动创建基金记录
        fund = Fund(
            fund_code=data.fund_code,
            fund_name=info["fund_name"],
            fund_type=info.get("fund_type", ""),
            latest_nav=nav if nav > 0 else None,
        )
        db.add(fund)
        db.flush()

    # 检查是否已有活跃持仓
    existing = db.query(Holding).filter(
        Holding.fund_code == data.fund_code,
        Holding.is_active == True,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该基金已有活跃持仓，请使用更新接口")

    holding = Holding(
        fund_code=data.fund_code,
        shares=data.shares,
        cost_price=data.cost_price,
        cost_amount=data.cost_amount or data.shares * data.cost_price,
        current_nav=float(fund.latest_nav or 0),
        current_value=data.shares * float(fund.latest_nav or 0),
        source=data.source,
        is_active=True,
    )
    # 计算盈亏
    holding.pnl_amount = holding.current_value - holding.cost_amount
    if holding.cost_amount > 0:
        holding.pnl_ratio = holding.pnl_amount / holding.cost_amount * 100

    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding.to_dict()


@router.put("/{fund_code}")
def update_holding(fund_code: str, data: HoldingUpdate, db: Session = Depends(get_db)):
    """修改持仓"""
    holding = db.query(Holding).filter(
        Holding.fund_code == fund_code,
        Holding.is_active == True,
    ).first()
    if not holding:
        raise HTTPException(status_code=404, detail="持仓不存在")

    if data.shares is not None:
        holding.shares = data.shares
    if data.cost_price is not None:
        holding.cost_price = data.cost_price
    if data.cost_amount is not None:
        holding.cost_amount = data.cost_amount

    # 重算市值和盈亏
    holding.current_value = float(holding.shares or 0) * float(holding.current_nav or 0)
    holding.pnl_amount = float(holding.current_value or 0) - float(holding.cost_amount or 0)
    if float(holding.cost_amount or 0) > 0:
        holding.pnl_ratio = holding.pnl_amount / float(holding.cost_amount) * 100

    db.commit()
    db.refresh(holding)
    return holding.to_dict()


@router.delete("/{fund_code}")
def delete_holding(fund_code: str, db: Session = Depends(get_db)):
    """清除持仓（标记为非活跃）"""
    holding = db.query(Holding).filter(
        Holding.fund_code == fund_code,
        Holding.is_active == True,
    ).first()
    if not holding:
        raise HTTPException(status_code=404, detail="持仓不存在")
    holding.is_active = False
    db.commit()
    return {"message": "持仓已清除"}
