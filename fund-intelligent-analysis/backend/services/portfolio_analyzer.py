"""
持仓分析服务
"""
from sqlalchemy.orm import Session
from backend.models.holding import Holding
from backend.models.fund import Fund


class PortfolioAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def get_portfolio_analysis(self) -> dict:
        """获取持仓综合分析"""
        holdings = self.db.query(Holding).filter(Holding.is_active == True).all()

        if not holdings:
            return {"message": "暂无持仓"}

        total_value = sum(float(h.current_value or 0) for h in holdings)
        total_cost = sum(float(h.cost_amount or 0) for h in holdings)
        total_pnl = total_value - total_cost

        # 按类型分布
        type_distribution = {}
        # 按盈亏分布
        pnl_distribution = {"profit": 0, "loss": 0, "breakeven": 0}

        holdings_detail = []
        for h in holdings:
            fund = self.db.query(Fund).filter(Fund.fund_code == h.fund_code).first()
            fund_type = fund.fund_type if fund else "未知"
            val = float(h.current_value or 0)
            pnl = float(h.pnl_amount or 0)

            # 类型分布
            if fund_type not in type_distribution:
                type_distribution[fund_type] = {"value": 0, "count": 0}
            type_distribution[fund_type]["value"] += val
            type_distribution[fund_type]["count"] += 1

            # 盈亏分布
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

        # 集中度分析
        max_weight = max(d["weight"] for d in holdings_detail) if holdings_detail else 0
        concentration = "高集中度" if max_weight > 50 else "中等集中度" if max_weight > 30 else "分散配置"

        return {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_ratio": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
            "holding_count": len(holdings),
            "type_distribution": {
                k: {"value": round(v["value"], 2), "count": v["count"],
                    "ratio": round(v["value"] / total_value * 100, 2) if total_value > 0 else 0}
                for k, v in type_distribution.items()
            },
            "pnl_distribution": pnl_distribution,
            "concentration": concentration,
            "max_weight_fund": max(holdings_detail, key=lambda x: x["weight"]) if holdings_detail else None,
            "holdings": holdings_detail,
        }
