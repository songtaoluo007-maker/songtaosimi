"""机构/主力资金流向 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date
from backend.database import get_db
from backend.models.capital_flow import CapitalFlow

router = APIRouter(prefix="/api/capital-flow", tags=["资金流向"])


@router.get("/latest")
def get_latest_flow(db: Session = Depends(get_db)):
    """最近交易日的资金流向汇总。无数据时自动触发采集。"""
    today = date.today()
    flows = db.query(CapitalFlow).filter(CapitalFlow.flow_date == today).all()
    if not flows:
        # 兜底：尝试最近有数据的日期
        latest_date = db.query(CapitalFlow.flow_date).order_by(
            CapitalFlow.flow_date.desc()
        ).first()
        if latest_date:
            flows = db.query(CapitalFlow).filter(
                CapitalFlow.flow_date == latest_date[0]
            ).all()
        # 如果完全没有数据，触发一次采集
        if not flows:
            try:
                from backend.services.capital_flow_collector import collect_all_capital_flows
                collect_all_capital_flows()
                flows = db.query(CapitalFlow).filter(CapitalFlow.flow_date == today).all()
            except Exception as e:
                from loguru import logger
                logger.warning(f"自动采集资金流失败: {e}")

    north = [f.to_dict() for f in flows if f.flow_type == "north_bound"]
    main_force = [f.to_dict() for f in flows if f.flow_type == "main_force"]
    margin = [f.to_dict() for f in flows if f.flow_type == "margin"]
    lhb = [f.to_dict() for f in flows if f.flow_type == "lhb"]
    national_team = [f.to_dict() for f in flows if f.flow_type == "national_team"]

    # 主力资金汇总
    mf_all = [f for f in main_force if f["symbol"] == "all"]
    mf_sectors = sorted(
        [f for f in main_force if f["symbol"] != "all"],
        key=lambda x: abs(x["net_inflow"]), reverse=True
    )

    return {
        "flow_date": str(flows[0].flow_date) if flows else str(today),
        "north_bound": {"items": north, "total_net": sum(f["net_inflow"] for f in north)},
        "main_force": {
            "summary": mf_all[0] if mf_all else None,
            "top_sectors": mf_sectors[:10],
        },
        "margin": {"items": margin},
        "lhb": {"items": lhb, "net_institution": sum(
            f["institution_buy"] - f["institution_sell"] for f in lhb
        )},
        "national_team": {
            "items": national_team,
            "stocks": len(national_team),
            "total_net": sum(f["net_inflow"] for f in national_team),
        },
    }


@router.get("/my-holdings-impact")
def get_holdings_flow_impact(db: Session = Depends(get_db)):
    """机构资金流对用户持仓的影响分析"""
    from backend.models.holding import Holding
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    if not holdings:
        return {"message": "暂无持仓", "impact": []}

    # 获取今日资金流数据
    today = date.today()
    flows = db.query(CapitalFlow).filter(CapitalFlow.flow_date == today).all()
    if not flows:
        latest_date = db.query(CapitalFlow.flow_date).order_by(CapitalFlow.flow_date.desc()).first()
        if latest_date:
            flows = db.query(CapitalFlow).filter(CapitalFlow.flow_date == latest_date[0]).all()

    # 主力资金全市场数据
    mf_all = [f for f in flows if f.flow_type == "main_force" and f.symbol == "all"]
    main_force_net = float(mf_all[0].net_inflow or 0) if mf_all else 0

    # 北向资金汇总
    nb_flows = [f for f in flows if f.flow_type == "north_bound"]
    nb_total = sum(float(f.net_inflow or 0) for f in nb_flows)

    # 按基金类型关联
    fund_types = {}
    for h in holdings:
        ft = h.fund.fund_type if h.fund else "混合型"
        if ft not in fund_types:
            fund_types[ft] = {"count": 0, "total_value": 0, "total_pnl": 0}
        fund_types[ft]["count"] += 1
        fund_types[ft]["total_value"] += float(h.current_value or 0)
        fund_types[ft]["total_pnl"] += float(h.pnl_amount or 0)

    impact = []
    total_value = sum(float(h.current_value or 0) for h in holdings)
    for ft, stats in fund_types.items():
        weight = stats["total_value"] / total_value * 100 if total_value > 0 else 0
        signal = "hold"
        if main_force_net < -500 and weight > 20:
            signal = "reduce"
        elif main_force_net > 100 and weight < 30:
            signal = "add"
        impact.append({
            "fund_type": ft,
            "count": stats["count"],
            "value": round(stats["total_value"], 2),
            "weight": round(weight, 1),
            "pnl": round(stats["total_pnl"], 2),
            "signal": signal,
        })

    impact.sort(key=lambda x: x["weight"], reverse=True)

    return {
        "flow_date": str(flows[0].flow_date) if flows else str(today),
        "main_force_net": round(main_force_net, 1),
        "north_bound_net": round(nb_total, 1),
        "market_signal": "主力大幅流出，谨慎" if main_force_net < -500 else ("主力流入，偏乐观" if main_force_net > 100 else "资金中性"),
        "impact": impact,
    }


@router.post("/refresh")
def refresh_capital_flows():
    """手动刷新资金流向数据"""
    try:
        from backend.services.capital_flow_collector import collect_all_capital_flows
        collect_all_capital_flows()
        return {"message": "资金流向数据已刷新"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/score")
def get_flow_score(db: Session = Depends(get_db)):
    """综合资金流评分 (-100 ~ +100)"""
    from backend.services.capital_flow_scorer import get_flow_score as _score
    return _score(db)


@router.get("/position-impact")
def get_flow_impact(db: Session = Depends(get_db)):
    """资金流向对持仓的影响映射"""
    from backend.services.capital_flow_scorer import get_flow_position_impact
    return get_flow_position_impact(db)
