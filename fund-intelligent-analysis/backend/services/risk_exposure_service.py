"""
组合风险暴露分析服务
基于基金标签 + 持仓权重，计算行业/主题/风格/集中度
"""
from sqlalchemy.orm import Session, joinedload
from backend.models.holding import Holding
from backend.models.fund_tag import FundTag


def _get_holdings_with_weight(db: Session) -> list[dict]:
    """获取持仓及其权重"""
    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
    total_value = sum(float(h.current_value or 0) for h in holdings)
    if total_value <= 0:
        return []

    result = []
    for h in holdings:
        fund = h.fund
        weight = float(h.current_value or 0) / total_value
        result.append({
            "fund_code": h.fund_code,
            "fund_name": fund.fund_name if fund else "",
            "weight": weight,
            "value": float(h.current_value or 0),
            "daily_pnl": float(h.daily_pnl or 0) if hasattr(h, 'daily_pnl') else 0,
        })
    return result


def _get_tags_map(db: Session) -> dict[str, list[FundTag]]:
    """获取所有持仓基金的标签映射 {fund_code: [tags]}"""
    holding_codes = [
        h.fund_code for h in
        db.query(Holding.fund_code).filter(Holding.is_active == True).distinct()
    ]
    tags = db.query(FundTag).filter(FundTag.fund_code.in_(holding_codes)).all()
    tag_map: dict[str, list[FundTag]] = {}
    for t in tags:
        tag_map.setdefault(t.fund_code, []).append(t)
    return tag_map


def get_industry_exposure(db: Session) -> dict:
    holdings = _get_holdings_with_weight(db)
    tags_map = _get_tags_map(db)
    exposure: dict[str, float] = {}
    details = []

    for h in holdings:
        fund_tags = tags_map.get(h["fund_code"], [])
        industry_tags = [t for t in fund_tags if t.tag_type == "industry"]
        for t in industry_tags:
            weighted = h["weight"] * float(t.tag_value or 1.0) * 100
            exposure[t.tag_name] = exposure.get(t.tag_name, 0) + weighted
        details.append({
            "fund_code": h["fund_code"],
            "fund_name": h["fund_name"],
            "weight_pct": round(h["weight"] * 100, 1),
            "industries": [{"name": t.tag_name, "value": t.tag_value} for t in industry_tags],
        })

    sorted_exp = sorted(exposure.items(), key=lambda x: x[1], reverse=True)
    return {
        "exposure": [{"name": k, "value": round(v, 1)} for k, v in sorted_exp if v > 0],
        "details": details,
    }


def get_theme_exposure(db: Session) -> dict:
    holdings = _get_holdings_with_weight(db)
    tags_map = _get_tags_map(db)
    exposure: dict[str, float] = {}

    for h in holdings:
        fund_tags = tags_map.get(h["fund_code"], [])
        for t in fund_tags:
            if t.tag_type == "theme":
                weighted = h["weight"] * float(t.tag_value or 1.0) * 100
                exposure[t.tag_name] = exposure.get(t.tag_name, 0) + weighted

    sorted_exp = sorted(exposure.items(), key=lambda x: x[1], reverse=True)
    return {
        "exposure": [{"name": k, "value": round(v, 1)} for k, v in sorted_exp if v > 0],
    }


def get_style_exposure(db: Session) -> dict:
    holdings = _get_holdings_with_weight(db)
    tags_map = _get_tags_map(db)
    exposure: dict[str, float] = {}

    for h in holdings:
        fund_tags = tags_map.get(h["fund_code"], [])
        for t in fund_tags:
            if t.tag_type == "style":
                weighted = h["weight"] * float(t.tag_value or 1.0) * 100
                exposure[t.tag_name] = exposure.get(t.tag_name, 0) + weighted

    sorted_exp = sorted(exposure.items(), key=lambda x: x[1], reverse=True)
    return {
        "exposure": [{"name": k, "value": round(v, 1)} for k, v in sorted_exp if v > 0],
    }


def get_concentration(db: Session) -> dict:
    holdings = _get_holdings_with_weight(db)
    tags_map = _get_tags_map(db)

    sorted_by_weight = sorted(holdings, key=lambda x: x["weight"], reverse=True)
    top1 = sorted_by_weight[0]["weight"] * 100 if len(sorted_by_weight) >= 1 else 0
    top3 = sum(h["weight"] for h in sorted_by_weight[:3]) * 100
    top5 = sum(h["weight"] for h in sorted_by_weight[:5]) * 100

    # 同主题集中度
    theme_funds: dict[str, list[str]] = {}
    for code, tags in tags_map.items():
        for t in tags:
            if t.tag_type == "theme":
                theme_funds.setdefault(t.tag_name, []).append(code)

    theme_concentration = {}
    for theme_name, codes in theme_funds.items():
        if len(codes) >= 2:
            theme_weight = sum(
                h["weight"] for h in holdings if h["fund_code"] in codes
            ) * 100
            theme_concentration[theme_name] = round(theme_weight, 1)

    # 高波动占比
    high_vol_weight = 0.0
    for h in holdings:
        tags = tags_map.get(h["fund_code"], [])
        for t in tags:
            if t.tag_type == "style" and t.tag_name in ("高波动",):
                high_vol_weight += h["weight"]
            if t.tag_type == "risk" and t.tag_name in ("高",):
                high_vol_weight += h["weight"]

    return {
        "top1_pct": round(top1, 1),
        "top3_pct": round(top3, 1),
        "top5_pct": round(top5, 1),
        "total_holdings": len(holdings),
        "theme_concentration": sorted(
            [{"theme": k, "weight_pct": v} for k, v in theme_concentration.items()],
            key=lambda x: x["weight_pct"], reverse=True,
        ),
        "high_volatility_pct": round(high_vol_weight * 100, 1),
        "warning": _concentration_warning(top1, top3, len(holdings), theme_concentration),
    }


def _concentration_warning(top1: float, top3: float, count: int, theme_conc: dict) -> str:
    warnings = []
    if top1 > 15:
        warnings.append(f"最大持仓占比 {top1:.0f}%＞15%")
    if top3 > 45:
        warnings.append(f"前3大持仓合计 {top3:.0f}%＞45%")
    high_theme = [(k, v) for k, v in theme_conc.items() if v > 40]
    for name, w in high_theme[:2]:
        warnings.append(f"{name}主题集中度 {w:.0f}%＞40%")
    if not warnings:
        return "组合分散度良好"
    return "；".join(warnings) + "，表面分散但实际风险集中"


def get_full_report(db: Session) -> dict:
    return {
        "industry": get_industry_exposure(db),
        "theme": get_theme_exposure(db),
        "style": get_style_exposure(db),
        "concentration": get_concentration(db),
    }
