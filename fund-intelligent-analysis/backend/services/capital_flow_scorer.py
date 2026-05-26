"""
资金流综合评分服务
将多维度资金流数据聚合为 -100 ~ +100 的单一评分
"""
from sqlalchemy.orm import Session, joinedload
from loguru import logger
from backend.models.capital_flow import CapitalFlow
from backend.models.holding import Holding
from backend.models.fund_tag import FundTag


def get_flow_score(db: Session) -> dict:
    """计算当日综合资金流评分"""
    from datetime import date

    today = date.today()
    flows = db.query(CapitalFlow).filter(CapitalFlow.flow_date == today).all()

    if not flows:
        # 尝试最近交易日
        latest_date = db.query(CapitalFlow.flow_date).order_by(
            CapitalFlow.flow_date.desc()
        ).first()
        if latest_date:
            flows = db.query(CapitalFlow).filter(
                CapitalFlow.flow_date == latest_date[0]
            ).all()

    if not flows:
        return {"score": 0, "status": "no_data", "summary": "暂无资金流数据"}

    # 各维度评分归一化到 -50 ~ +50
    score = 0.0
    details = []

    for f in flows:
        flow_type = f.flow_type or ""
        net_value = float(f.net_amount or 0)
        # 简易归一化：将各维度的净流入映射到 -50~+50
        if flow_type in ("north_bound",):
            dimension_score = max(-50, min(50, net_value / 1e8 * 0.5))
            score += dimension_score
            details.append({"dimension": "北向资金", "net": round(net_value / 1e8, 2), "unit": "亿", "contribution": round(dimension_score, 1)})
        elif flow_type in ("main_force",):
            dimension_score = max(-50, min(50, net_value / 1e8 * 0.3))
            score += dimension_score
            details.append({"dimension": "主力资金", "net": round(net_value / 1e8, 2), "unit": "亿", "contribution": round(dimension_score, 1)})
        elif flow_type in ("super_large",):
            dimension_score = max(-50, min(50, net_value / 1e8 * 0.3))
            score += dimension_score
            details.append({"dimension": "超大单", "net": round(net_value / 1e8, 2), "unit": "亿", "contribution": round(dimension_score, 1)})
        elif flow_type in ("large_order",):
            dimension_score = max(-50, min(50, net_value / 1e8 * 0.2))
            score += dimension_score
            details.append({"dimension": "大单", "net": round(net_value / 1e8, 2), "unit": "亿", "contribution": round(dimension_score, 1)})
        elif flow_type in ("institution", "national_team"):
            dimension_score = max(-50, min(50, net_value / 1e8 * 0.4))
            score += dimension_score
            label = "机构席位" if flow_type == "institution" else "国家队"
            details.append({"dimension": label, "net": round(net_value / 1e8, 2), "unit": "亿", "contribution": round(dimension_score, 1)})

    final_score = round(max(-100, min(100, score)), 1)

    if final_score >= 30:
        status = "资金偏强"
        summary = "多维度资金流入明显，市场承接力度较强"
    elif final_score >= 10:
        status = "资金中性偏强"
        summary = "部分维度资金流入，整体方向偏正面"
    elif final_score >= -10:
        status = "资金中性"
        summary = "资金流入出基本平衡，方向不明确"
    elif final_score >= -30:
        status = "资金中性偏弱"
        summary = "部分维度资金流出，市场承接力度一般"
    else:
        status = "资金偏弱"
        summary = "多维度资金流出明显，市场承接力度不足"

    return {
        "score": final_score,
        "status": status,
        "summary": summary,
        "details": details,
    }


def get_flow_position_impact(db: Session) -> list[dict]:
    """资金流向对持仓的影响：按板块资金流映射到用户持仓基金"""
    from datetime import date

    today = date.today()
    flows = db.query(CapitalFlow).filter(CapitalFlow.flow_date == today).all()
    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()

    tag_map: dict[str, list[str]] = {}
    tags = db.query(FundTag).all()
    for t in tags:
        tag_map.setdefault(t.tag_name, []).append(t.fund_code)

    impacts = []
    for h in holdings:
        fund = h.fund
        fund_tags = [t for t in tags if t.fund_code == h.fund_code]
        theme_names = [t.tag_name for t in fund_tags if t.tag_type == "theme"]

        # 检查资金流方向对应的板块是否命中该基金的标签
        impact_note = ""
        direction = "neutral"
        for f in flows:
            flow_name = f.flow_name or ""
            net = float(f.net_amount or 0)
            for theme in theme_names:
                if theme in flow_name or flow_name in theme:
                    if net > 100:
                        impact_note = f"{flow_name}资金流入，偏正面影响"
                        direction = "positive"
                    elif net < -100:
                        impact_note = f"{flow_name}资金流出，偏负面影响"
                        direction = "negative"

        impacts.append({
            "fund_code": h.fund_code,
            "fund_name": fund.fund_name if fund else "",
            "direction": direction,
            "impact_note": impact_note or "无明显资金流影响",
        })

    return impacts
