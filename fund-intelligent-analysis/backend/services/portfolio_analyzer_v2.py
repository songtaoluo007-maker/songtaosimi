"""
持仓分析服务 — V2

V2 改动：
- 修复 BUG：循环内 `fund.fund_name` 未定义（应为 `h.fund.fund_name`）
- 用 joinedload 避免 N+1
- 空持仓时返回完整空结构，避免前端 v-if 缺失字段
- max_weight_fund 改为返回字典 {code,name,weight}，与 holdings_detail 一致
"""
from sqlalchemy.orm import Session, joinedload
from backend.models.holding import Holding


class PortfolioAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def get_portfolio_analysis(self) -> dict:
        holdings = (
            self.db.query(Holding)
            .options(joinedload(Holding.fund))
            .filter(Holding.is_active == True)
            .all()
        )

        if not holdings:
            return {
                "total_value": 0,
                "total_cost": 0,
                "total_pnl": 0,
                "total_pnl_ratio": 0,
                "holding_count": 0,
                "type_distribution": {},
                "pnl_distribution": {"profit": 0, "loss": 0, "breakeven": 0},
                "concentration": "暂无持仓",
                "max_weight_fund": None,
                "holdings": [],
                "message": "暂无持仓",
            }

        total_value = sum(float(h.current_value or 0) for h in holdings)
        total_cost = sum(float(h.cost_amount or 0) for h in holdings)
        total_pnl = total_value - total_cost

        type_distribution: dict[str, dict] = {}
        pnl_distribution = {"profit": 0, "loss": 0, "breakeven": 0}
        holdings_detail = []

        for h in holdings:
            fund = h.fund  # 关键修复：原 v1 直接用 `fund` 是 NameError
            fund_type = fund.fund_type if fund else "未知"
            val = float(h.current_value or 0)
            pnl = float(h.pnl_amount or 0)

            bucket = type_distribution.setdefault(fund_type, {"value": 0.0, "count": 0})
            bucket["value"] += val
            bucket["count"] += 1

            if pnl > 0:
                pnl_distribution["profit"] += 1
            elif pnl < 0:
                pnl_distribution["loss"] += 1
            else:
                pnl_distribution["breakeven"] += 1

            holdings_detail.append({
                "fund_code": h.fund_code,
                "fund_name": fund.fund_name if fund else "",
                "fund_type": fund_type,
                "shares": float(h.shares or 0),
                "cost_amount": float(h.cost_amount or 0),
                "current_value": val,
                "pnl_amount": pnl,
                "pnl_ratio": float(h.pnl_ratio or 0),
                "weight": round(val / total_value * 100, 2) if total_value > 0 else 0,
            })

        max_weight = max((d["weight"] for d in holdings_detail), default=0)
        if max_weight > 50:
            concentration = "高集中度"
        elif max_weight > 30:
            concentration = "中等集中度"
        else:
            concentration = "分散配置"

        max_weight_fund = (
            max(holdings_detail, key=lambda x: x["weight"]) if holdings_detail else None
        )

        return {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_ratio": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
            "holding_count": len(holdings),
            "type_distribution": {
                k: {
                    "value": round(v["value"], 2),
                    "count": v["count"],
                    "ratio": round(v["value"] / total_value * 100, 2) if total_value > 0 else 0,
                }
                for k, v in type_distribution.items()
            },
            "pnl_distribution": pnl_distribution,
            "concentration": concentration,
            "max_weight_fund": max_weight_fund,
            "holdings": holdings_detail,
        }
