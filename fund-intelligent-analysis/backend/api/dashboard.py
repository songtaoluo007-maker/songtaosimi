from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
from backend.database import get_db
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.models.news import News
from backend.models.ai_advice import AiAdvice
from backend.models.fund import Fund

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """总览数据"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()

    total_value = sum(float(h.current_value or 0) for h in holdings)
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_ratio = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    # 今日盈亏：用今日估值和昨日净值差算（简化：用最新盈亏）
    today_pnl = total_pnl  # 简化处理

    # 最新AI建议
    latest_advice = db.query(AiAdvice).order_by(AiAdvice.advice_date.desc()).first()

    return {
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_ratio": round(total_pnl_ratio, 2),
        "today_pnl": round(today_pnl, 2),
        "holding_count": len(holdings),
        "latest_advice_date": str(latest_advice.advice_date) if latest_advice else None,
    }


@router.get("/command-center")
def get_command_center(db: Session = Depends(get_db)):
    """私人基金工作台：资产、风险、AI建议和数据新鲜度。"""
    today = date.today()
    try:
        from backend.services.market_collector import is_trading_day
        trading_day = bool(is_trading_day())
    except Exception:
        trading_day = today.weekday() < 5
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    total_value = sum(float(h.current_value or 0) for h in holdings)
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_ratio = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    positions = []
    for h in holdings:
        fund = db.query(Fund).filter(Fund.fund_code == h.fund_code).first()
        value = float(h.current_value or 0)
        pnl = float(h.pnl_amount or 0)
        pnl_ratio = float(h.pnl_ratio or 0)
        weight = value / total_value * 100 if total_value > 0 else 0
        positions.append({
            "fund_code": h.fund_code,
            "fund_name": fund.fund_name if fund else "",
            "fund_type": fund.fund_type if fund else "未知",
            "current_value": round(value, 2),
            "pnl_amount": round(pnl, 2),
            "pnl_ratio": round(pnl_ratio, 2),
            "weight": round(weight, 2),
        })
    positions.sort(key=lambda x: x["current_value"], reverse=True)

    top_weight = positions[0]["weight"] if positions else 0
    loss_positions = [p for p in positions if p["pnl_amount"] < 0]
    gain_positions = [p for p in positions if p["pnl_amount"] >= 0]

    latest_advice = db.query(AiAdvice).order_by(
        AiAdvice.advice_date.desc(),
        AiAdvice.advice_time.desc(),
    ).first()
    latest_index = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == "index",
        MarketSnapshot.snapshot_date == today,
    ).order_by(MarketSnapshot.snapshot_time.desc()).first()
    latest_fund_estimate = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == "fund",
        MarketSnapshot.snapshot_date == today,
    ).order_by(MarketSnapshot.snapshot_time.desc()).first()
    recent_news_count = db.query(News).filter(
        News.publish_time >= datetime.combine(today - timedelta(days=3), datetime.min.time()),
    ).count()

    risk_flags = []
    if top_weight >= 25:
        risk_flags.append({"level": "high", "title": "单基金集中度偏高", "detail": f"最大持仓占比 {top_weight:.1f}%"})
    elif top_weight >= 15:
        risk_flags.append({"level": "medium", "title": "单基金集中度需关注", "detail": f"最大持仓占比 {top_weight:.1f}%"})
    if len(holdings) > 20:
        risk_flags.append({"level": "medium", "title": "持仓数量偏多", "detail": f"当前 {len(holdings)} 只基金，复盘成本较高"})
    if not latest_fund_estimate:
        title = "缺少交易日基金估值" if trading_day else "休市期间暂无当日估值"
        detail = "尾盘建议会自动尝试刷新" if trading_day else "休市日将沿用最近交易日估值复盘"
        risk_flags.append({"level": "medium", "title": title, "detail": detail})
    if not latest_advice:
        risk_flags.append({"level": "medium", "title": "暂无AI建议", "detail": "可在AI顾问页手动生成"})
    if not risk_flags:
        risk_flags.append({"level": "low", "title": "关键风险正常", "detail": "集中度和数据新鲜度暂无明显异常"})

    actions = latest_advice.actions if latest_advice and latest_advice.actions else []
    action_counts = {
        "add": len([a for a in actions if a.get("action") == "add"]),
        "reduce": len([a for a in actions if a.get("action") == "reduce"]),
        "hold": len([a for a in actions if a.get("action") == "hold"]),
    }

    return {
        "as_of": str(today),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "portfolio": {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_ratio": round(total_pnl_ratio, 2),
            "holding_count": len(holdings),
            "gain_count": len(gain_positions),
            "loss_count": len(loss_positions),
            "top_weight": round(top_weight, 2),
        },
        "latest_advice": latest_advice.to_dict() if latest_advice else None,
        "action_counts": action_counts,
        "top_positions": positions[:8],
        "risk_flags": risk_flags,
        "data_freshness": {
            "is_trading_day": trading_day,
            "latest_index_time": str(latest_index.snapshot_time) if latest_index else None,
            "latest_fund_estimate_time": str(latest_fund_estimate.snapshot_time) if latest_fund_estimate else None,
            "recent_news_count": recent_news_count,
        },
    }


@router.get("/pnl-curve")
def get_pnl_curve(days: int = 30, db: Session = Depends(get_db)):
    """盈亏曲线数据（按日汇总）"""
    # 基于market_snapshots中的基金估值数据构建曲线
    start_date = date.today() - timedelta(days=days)
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == "fund",
        MarketSnapshot.snapshot_date >= start_date,
    ).order_by(MarketSnapshot.snapshot_date).all()

    # 按日期汇总
    daily_data = {}
    for s in snapshots:
        d = str(s.snapshot_date)
        if d not in daily_data:
            daily_data[d] = {"date": d, "total_value": 0, "total_cost": 0}
        daily_data[d]["total_value"] += float(s.price or 0)  # 简化：用price存估值

    # 补充持仓成本
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)

    result = []
    for d in sorted(daily_data.keys()):
        v = daily_data[d]
        pnl = v["total_value"] - total_cost
        result.append({
            "date": d,
            "total_value": round(v["total_value"], 2),
            "pnl": round(pnl, 2),
        })

    return result


@router.get("/asset-allocation")
def get_asset_allocation(db: Session = Depends(get_db)):
    """资产配置分布"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()

    total_value = sum(float(h.current_value or 0) for h in holdings)
    allocation = {}
    for h in holdings:
        fund_type = h.fund.fund_type if h.fund else "未知"
        val = float(h.current_value or 0)
        allocation[fund_type] = allocation.get(fund_type, 0) + val

    result = []
    for k, v in allocation.items():
        result.append({
            "type": k,
            "value": round(v, 2),
            "ratio": round(v / total_value * 100, 2) if total_value > 0 else 0,
        })
    return result
