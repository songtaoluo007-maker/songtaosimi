"""
持仓重叠度分析 — P0.3

老基民经典陷阱："5 只医药基金各 15% → 系统说分散，其实就是 1 只医药基金。"

算法：
- 加权重叠度 = Σ min(A.weight[stock], B.weight[stock])  for stock in A ∩ B
- 真实分散度评分 = 100 - 平均两两重叠度（0-100，越高越分散）
- 重复重仓股 = 同时被多只持仓基金重仓的股票，按"组合实际暴露"排序

暴露计算：
  stock_exposure_in_portfolio = Σ (fund_weight_in_portfolio × stock_weight_in_fund)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy.orm import Session, joinedload

from backend.models.fund_top_holding import FundTopHolding
from backend.models.holding import Holding


def _latest_quarter_per_fund(db: Session, fund_codes: list[str]) -> dict[str, str]:
    """每只基金取最新一个 quarter（披露季度可能不同）"""
    if not fund_codes:
        return {}
    rows = (
        db.query(FundTopHolding.fund_code, FundTopHolding.quarter)
        .filter(FundTopHolding.fund_code.in_(fund_codes))
        .all()
    )
    by_code: dict[str, str] = {}
    for code, q in rows:
        if not q:
            continue
        # 字典序倒序即时间倒序（'2025Q4' > '2025Q3' > '2025Q2'）
        if code not in by_code or q > by_code[code]:
            by_code[code] = q
    return by_code


def _fund_holdings_map(db: Session) -> tuple[dict[str, dict[str, float]],
                                             dict[str, dict[str, str]]]:
    """{fund_code: {stock_code: weight_pct}} + {fund_code: {stock_code: stock_name}}"""
    active = db.query(Holding).filter(Holding.is_active == True).all()
    codes = [h.fund_code for h in active]
    latest_q = _latest_quarter_per_fund(db, codes)

    weights: dict[str, dict[str, float]] = defaultdict(dict)
    stock_names: dict[str, str] = {}
    for code in codes:
        q = latest_q.get(code)
        if not q:
            continue
        rows = (
            db.query(FundTopHolding)
            .filter(
                FundTopHolding.fund_code == code,
                FundTopHolding.quarter == q,
            )
            .all()
        )
        for r in rows:
            if not r.stock_code:
                continue
            weights[code][r.stock_code] = float(r.weight_pct or 0)
            stock_names[r.stock_code] = r.stock_name or r.stock_code
    return weights, stock_names


def calc_overlap_report(db: Session) -> dict:
    """组合两两重叠度 + 真实分散度 + 重复重仓股"""
    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    if len(holdings) < 1:
        return _empty_report("暂无持仓")

    fund_weights_in_portfolio: dict[str, float] = {}
    total_value = sum(float(h.current_value or 0) for h in holdings)
    if total_value <= 0:
        return _empty_report("持仓总市值为 0")
    for h in holdings:
        fund_weights_in_portfolio[h.fund_code] = float(h.current_value or 0) / total_value

    stock_weights, stock_names = _fund_holdings_map(db)

    funds_with_data = [c for c in fund_weights_in_portfolio if c in stock_weights]
    funds_without_data = [c for c in fund_weights_in_portfolio if c not in stock_weights]

    # 两两加权重叠
    pairs = []
    overlap_sum = 0.0
    overlap_count = 0
    fund_name_by_code = {h.fund_code: (h.fund.fund_name if h.fund else "") for h in holdings}
    for i, a in enumerate(funds_with_data):
        for b in funds_with_data[i + 1:]:
            common = set(stock_weights[a]) & set(stock_weights[b])
            if not common:
                weighted = 0.0
            else:
                weighted = sum(
                    min(stock_weights[a][s], stock_weights[b][s]) for s in common
                )
            pairs.append({
                "fund_a": a,
                "fund_a_name": fund_name_by_code.get(a, ""),
                "fund_b": b,
                "fund_b_name": fund_name_by_code.get(b, ""),
                "overlap_pct": round(weighted, 2),
                "common_count": len(common),
            })
            overlap_sum += weighted
            overlap_count += 1
    avg_overlap = overlap_sum / overlap_count if overlap_count else 0.0
    diversification = max(0.0, 100.0 - avg_overlap)

    # 重复重仓股（按组合实际暴露排序）
    stock_to_funds: dict[str, list[dict]] = defaultdict(list)
    for fund_code, stocks in stock_weights.items():
        portfolio_w = fund_weights_in_portfolio.get(fund_code, 0)
        if portfolio_w <= 0:
            continue
        for stock_code, weight in stocks.items():
            stock_to_funds[stock_code].append({
                "fund_code": fund_code,
                "fund_name": fund_name_by_code.get(fund_code, ""),
                "weight_in_fund": round(weight, 2),
                "exposure": round(portfolio_w * weight, 4),
            })

    duplicated_stocks = []
    single_stock_top = []
    for stock_code, funds in stock_to_funds.items():
        total_exposure = sum(f["exposure"] for f in funds)
        row = {
            "stock_code": stock_code,
            "stock_name": stock_names.get(stock_code, stock_code),
            "fund_count": len(funds),
            "total_exposure_pct": round(total_exposure, 2),
            "via_funds": [{"fund_code": f["fund_code"],
                           "fund_name": f["fund_name"],
                           "weight_in_fund": f["weight_in_fund"]} for f in funds],
        }
        single_stock_top.append(row)
        if len(funds) >= 2:
            duplicated_stocks.append(row)
    duplicated_stocks.sort(key=lambda x: x["total_exposure_pct"], reverse=True)
    single_stock_top.sort(key=lambda x: x["total_exposure_pct"], reverse=True)

    warning = _build_warning(avg_overlap, duplicated_stocks, single_stock_top)

    # 热力图矩阵 — 用于前端 echarts heatmap
    heatmap = []
    code_to_idx = {code: idx for idx, code in enumerate(funds_with_data)}
    for p in pairs:
        i = code_to_idx[p["fund_a"]]
        j = code_to_idx[p["fund_b"]]
        heatmap.append([i, j, p["overlap_pct"]])
        heatmap.append([j, i, p["overlap_pct"]])  # 对称
    for code, idx in code_to_idx.items():
        heatmap.append([idx, idx, 100.0])  # 对角线自身重叠 100%

    return {
        "diversification_score": round(diversification, 1),
        "avg_overlap_pct": round(avg_overlap, 2),
        "max_overlap_pct": round(max([p["overlap_pct"] for p in pairs], default=0), 2),
        "pairs": sorted(pairs, key=lambda x: x["overlap_pct"], reverse=True),
        "duplicated_stocks": duplicated_stocks[:20],
        "single_stock_top": single_stock_top[:10],
        "heatmap": {
            "labels": [{"code": c, "name": fund_name_by_code.get(c, "")} for c in funds_with_data],
            "data": heatmap,
        },
        "data_coverage": {
            "with_data": funds_with_data,
            "without_data": funds_without_data,
            "coverage_pct": round(len(funds_with_data) / max(len(holdings), 1) * 100, 1),
            "note": "未覆盖的基金需要执行 P0.3 持股采集后才能纳入计算" if funds_without_data else "",
        },
        "warning": warning,
    }


def _build_warning(avg_overlap: float, dup_stocks: list[dict],
                   single_top: list[dict]) -> str:
    parts: list[str] = []
    if avg_overlap > 30:
        parts.append(f"组合实际分散度低 — 平均两两重叠 {avg_overlap:.1f}%（建议替换部分相似度高的基金）")
    elif avg_overlap > 20:
        parts.append(f"分散度一般 — 平均重叠 {avg_overlap:.1f}%")
    if single_top and single_top[0]["total_exposure_pct"] > 5:
        s = single_top[0]
        parts.append(
            f"单只股票暴露过高 — {s['stock_name']}({s['stock_code']})"
            f"合计暴露 {s['total_exposure_pct']:.2f}%"
        )
    if dup_stocks and dup_stocks[0]["fund_count"] >= 3:
        s = dup_stocks[0]
        parts.append(
            f"{s['stock_name']} 被 {s['fund_count']} 只基金共同重仓 — 风格集中"
        )
    if not parts:
        return "组合实际分散度良好"
    return "；".join(parts)


def _empty_report(message: str) -> dict:
    return {
        "diversification_score": 0,
        "avg_overlap_pct": 0,
        "max_overlap_pct": 0,
        "pairs": [],
        "duplicated_stocks": [],
        "single_stock_top": [],
        "heatmap": {"labels": [], "data": []},
        "data_coverage": {"with_data": [], "without_data": [],
                          "coverage_pct": 0, "note": message},
        "warning": message,
    }
