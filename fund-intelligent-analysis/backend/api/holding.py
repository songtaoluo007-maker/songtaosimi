from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models.holding import Holding
from backend.models.fund import Fund
from backend.schemas.holding import HoldingCreate, HoldingUpdate, HoldingResponse, HoldingSummary
from backend.services.fund_nav_collector import fetch_fund_info, fetch_latest_nav

router = APIRouter(prefix="/api/holdings", tags=["持仓管理"])


@router.get("")
def list_holdings(is_active: Optional[bool] = True, db: Session = Depends(get_db)):
    """获取当前持仓列表"""
    query = db.query(Holding).filter(Holding.is_active == is_active)
    holdings = query.all()
    result = []
    for h in holdings:
        d = h.to_dict()
        result.append(d)
    return result


@router.get("/summary")
def get_holdings_summary(db: Session = Depends(get_db)):
    """持仓汇总统计"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()

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

    holdings = db.query(Holding).filter(Holding.is_active == True).all()
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
                changes = []
                for vals in by_symbol.values():
                    if len(vals) >= 2 and vals[0]:
                        changes.append((vals[-1] - vals[0]) / vals[0] * 100)
                if changes:
                    portfolio_return = sum(changes) / len(changes)
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
