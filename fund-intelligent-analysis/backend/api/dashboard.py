from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import date, datetime, timedelta
from backend.database import get_db
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.models.news import News
from backend.models.ai_advice import AiAdvice

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)) -> dict:
    """总览数据"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()

    total_value = sum(float(h.current_value or 0) for h in holdings)
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_ratio = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    # 今日盈亏：基于当日基金快照的涨跌幅计算
    today_snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == "fund",
        MarketSnapshot.snapshot_date == date.today(),
    ).all()
    snap_map = {s.symbol.replace("fund_", ""): s for s in today_snapshots}
    today_pnl = sum(
        float(h.current_value or 0) * float(snap_map[h.fund_code].change_pct or 0) / 100
        for h in holdings if h.fund_code in snap_map
    )

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
def get_decision_command_center(db: Session = Depends(get_db)):
    """私人基金工作台：资产、收益、风险、AI动作和机会池的一屏决策摘要。"""
    today = date.today()
    try:
        from backend.services.market_collector import is_trading_day

        trading_day = bool(is_trading_day())
    except Exception:
        trading_day = today.weekday() < 5

    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
    total_value = sum(float(h.current_value or 0) for h in holdings)
    total_cost = sum(float(h.cost_amount or 0) for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_ratio = total_pnl / total_cost * 100 if total_cost > 0 else 0

    positions = []
    exposure = {}
    for h in holdings:
        fund = h.fund
        value = float(h.current_value or 0)
        pnl = float(h.pnl_amount or 0)
        daily_pnl = float(h.daily_pnl or 0)
        fund_type = fund.fund_type if fund else "未知"
        exposure[fund_type] = exposure.get(fund_type, 0) + value
        positions.append({
            "fund_code": h.fund_code,
            "fund_name": fund.fund_name if fund else "",
            "fund_type": fund_type,
            "current_value": round(value, 2),
            "pnl_amount": round(pnl, 2),
            "pnl_ratio": round(float(h.pnl_ratio or 0), 2),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_ratio": round(float(h.daily_pnl_ratio or 0), 2),
            "daily_pnl_date": h.daily_pnl_date.isoformat() if h.daily_pnl_date else "",
            "weight": round(value / total_value * 100, 2) if total_value > 0 else 0,
        })

    positions.sort(key=lambda x: x["current_value"], reverse=True)
    daily_sorted = sorted(positions, key=lambda x: x["daily_pnl"], reverse=True)
    total_daily_pnl = sum(p["daily_pnl"] for p in positions)
    total_daily_base = total_value - total_daily_pnl
    total_daily_pnl_ratio = total_daily_pnl / total_daily_base * 100 if total_daily_base > 0 else 0
    try:
        from backend.services.return_metrics_v3 import calc_portfolio_drawdown, calc_portfolio_xirr

        portfolio_xirr = calc_portfolio_xirr(db)
        drawdown = calc_portfolio_drawdown(db)
    except Exception:
        portfolio_xirr = 0
        drawdown = {"max_dd": 0, "current_dd": 0, "peak_date": None, "trough_date": None, "recovery_days": 0}
    exposure_rows = [
        {"name": name, "value": round(value, 2), "ratio": round(value / total_value * 100, 2) if total_value else 0}
        for name, value in sorted(exposure.items(), key=lambda item: item[1], reverse=True)
    ]

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

    benchmark = {
        "name": "沪深300",
        "price": round(float(latest_index.price or 0), 2) if latest_index else 0,
        "change_pct": round(float(latest_index.change_pct or 0), 2) if latest_index else 0,
        "updated_at": str(latest_index.snapshot_time) if latest_index else None,
    }

    opportunities = []
    try:
        from backend.services.market_collector import get_board_rankings

        for board_type, label in [("sector", "行业"), ("concept", "概念")]:
            ranking = get_board_rankings(board_type, 20, live=False)
            for item in ranking.get("heat_top", [])[:6]:
                opportunities.append({
                    "board_type": board_type,
                    "label": label,
                    "name": item.get("name"),
                    "change_pct": round(float(item.get("change_pct") or 0), 2),
                    "heat_score": round(float(item.get("heat_score") or 0), 0),
                    "main_net_inflow": round(float(item.get("main_net_inflow") or 0), 2),
                    "updated_at": item.get("updated_at"),
                })
        opportunities = sorted(opportunities, key=lambda x: x["heat_score"], reverse=True)[:8]
    except Exception:
        opportunities = []

    top_weight = positions[0]["weight"] if positions else 0
    risk_flags = []
    if top_weight >= 25:
        risk_flags.append({"level": "high", "title": "单只基金集中度偏高", "detail": f"最大持仓占比 {top_weight:.1f}%"})
    elif top_weight >= 15:
        risk_flags.append({"level": "medium", "title": "单只基金集中度需关注", "detail": f"最大持仓占比 {top_weight:.1f}%"})
    if len(holdings) > 20:
        risk_flags.append({"level": "medium", "title": "持仓数量偏多", "detail": f"当前 {len(holdings)} 只基金，复盘成本较高"})
    if not latest_fund_estimate:
        title = "缺少交易日基金估值" if trading_day else "休市期间暂无当日估值"
        detail = "尾盘建议会自动尝试刷新" if trading_day else "休市日展示最近交易日和本地持仓数据"
        risk_flags.append({"level": "medium", "title": title, "detail": detail})
    if not latest_advice:
        risk_flags.append({"level": "medium", "title": "暂无AI建议", "detail": "可在AI顾问页生成最新建议"})
    if not risk_flags:
        risk_flags.append({"level": "low", "title": "关键风险正常", "detail": "集中度和数据新鲜度暂未发现明显异常"})

    actions = latest_advice.actions if latest_advice and latest_advice.actions else []
    action_counts = {
        "add": len([a for a in actions if a.get("action") == "add"]),
        "reduce": len([a for a in actions if a.get("action") == "reduce"]),
        "hold": len([a for a in actions if a.get("action") == "hold"]),
    }
    if latest_advice:
        if action_counts["reduce"] > 0:
            primary_action = "优先控风险"
        elif action_counts["add"] > 0:
            primary_action = "存在加仓机会"
        else:
            primary_action = "以持有观察为主"
    else:
        primary_action = "等待AI建议"

    focus_items = []
    if daily_sorted:
        top_gain = daily_sorted[0]
        top_loss = daily_sorted[-1]
        focus_items.append(f"贡献最大：{top_gain['fund_name'] or top_gain['fund_code']} {top_gain['daily_pnl']:+.2f}元")
        focus_items.append(f"拖累最大：{top_loss['fund_name'] or top_loss['fund_code']} {top_loss['daily_pnl']:+.2f}元")
    if opportunities:
        focus_items.append(f"机会池优先看：{opportunities[0]['name']}，热度 {opportunities[0]['heat_score']:.0f}")
    if risk_flags:
        focus_items.append(f"首要风险：{risk_flags[0]['title']}")

    # ——— V2 新增：结构化今日关注 ———
    today_focus = {
        "top_contributor": None,
        "top_dragger": None,
        "top_opportunity": None,
        "market_signal": None,
    }
    if daily_sorted:
        top_g = daily_sorted[0]
        top_l = daily_sorted[-1]
        today_focus["top_contributor"] = {
            "fund_code": top_g["fund_code"],
            "fund_name": top_g["fund_name"],
            "daily_pnl": top_g["daily_pnl"],
            "daily_pnl_ratio": top_g["daily_pnl_ratio"],
        }
        today_focus["top_dragger"] = {
            "fund_code": top_l["fund_code"],
            "fund_name": top_l["fund_name"],
            "daily_pnl": top_l["daily_pnl"],
            "daily_pnl_ratio": top_l["daily_pnl_ratio"],
        }
    if opportunities:
        o = opportunities[0]
        today_focus["top_opportunity"] = {
            "name": o["name"],
            "board_type": o["board_type"],
            "change_pct": o["change_pct"],
            "heat_score": o["heat_score"],
        }
    if benchmark and benchmark.get("change_pct") is not None:
        direction = "偏强" if benchmark["change_pct"] > 0 else ("偏弱" if benchmark["change_pct"] < 0 else "震荡")
        today_focus["market_signal"] = f"沪深300 {direction} {benchmark['change_pct']:+.2f}%"

    # ——— V2 新增：AI 结构化摘要 ———
    ai_summary = None
    if latest_advice:
        ai_summary = {
            "advice_date": str(latest_advice.advice_date) if latest_advice.advice_date else None,
            "market_view": latest_advice.market_view,
            "risk_level": latest_advice.risk_level,
            "overall_suggestion": (latest_advice.overall_suggestion or "")[:120],
            "action_counts": action_counts,
        }
        # 有结构化输出时提取关键字段
        if latest_advice.structured_output:
            import json
            try:
                s = json.loads(latest_advice.structured_output)
                ai_summary["suggested_action"] = s.get("suggested_action", {}).get("action", "")
                ai_summary["confidence"] = s.get("suggested_action", {}).get("confidence", 0)
                ai_summary["position"] = s.get("suggested_action", {}).get("position", "")
                ai_summary["summary"] = s.get("summary", "")
                ai_summary["key_reasons"] = s.get("key_reasons", [])[:3]
                ai_summary["risk_warning"] = s.get("risk_warning", "")
            except Exception:
                pass

    # ——— V2 新增：风险暴露摘要 ———
    risk_summary = None
    try:
        from backend.services.risk_exposure_service import get_concentration, get_industry_exposure
        conc = get_concentration(db)
        ind = get_industry_exposure(db)
        risk_summary = {
            "top1_pct": conc.get("top1_pct", 0),
            "top3_pct": conc.get("top3_pct", 0),
            "high_volatility_pct": conc.get("high_volatility_pct", 0),
            "concentration_warning": conc.get("warning", ""),
            "top_industries": [e for e in (ind.get("exposure") or [])[:3]],
        }
    except Exception:
        pass

    return {
        "as_of": str(today),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "portfolio": {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_ratio": round(total_pnl_ratio, 2),
            "portfolio_xirr": portfolio_xirr,
            "max_drawdown": drawdown.get("max_dd", 0),
            "current_drawdown": drawdown.get("current_dd", 0),
            "drawdown_peak_date": drawdown.get("peak_date"),
            "drawdown_trough_date": drawdown.get("trough_date"),
            "drawdown_recovery_days": drawdown.get("recovery_days", 0),
            "total_daily_pnl": round(total_daily_pnl, 2),
            "total_daily_pnl_ratio": round(total_daily_pnl_ratio, 2),
            "holding_count": len(holdings),
            "gain_count": len([p for p in positions if p["daily_pnl"] >= 0]),
            "loss_count": len([p for p in positions if p["daily_pnl"] < 0]),
            "top_weight": round(top_weight, 2),
        },
        "decision": {
            "primary_action": primary_action,
            "focus_items": focus_items,
            "benchmark": benchmark,
        },
        "latest_advice": latest_advice.to_dict() if latest_advice else None,
        "action_counts": action_counts,
        "top_positions": positions[:8],
        "daily_gainers": daily_sorted[:5],
        "daily_losers": list(reversed(daily_sorted[-5:])),
        "exposure": exposure_rows,
        "opportunities": opportunities,
        "risk_flags": risk_flags,
        "today_focus": today_focus,
        "ai_summary": ai_summary,
        "risk_summary": risk_summary,
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

    # 按日期汇总组合市值：shares * nav
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    holding_map = {h.fund_code: h for h in holdings}

    daily_value = {}
    for s in snapshots:
        fund_code = s.symbol.replace("fund_", "")
        holding = holding_map.get(fund_code)
        if not holding:
            continue
        d = str(s.snapshot_date)
        shares = float(holding.shares or 0)
        nav = float(s.price or 0)
        daily_value[d] = daily_value.get(d, 0) + shares * nav

    total_cost = sum(float(h.cost_amount or 0) for h in holdings)

    result = []
    for d in sorted(daily_value.keys()):
        v = daily_value[d]
        result.append({
            "date": d,
            "total_value": round(v, 2),
            "pnl": round(v - total_cost, 2),
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
