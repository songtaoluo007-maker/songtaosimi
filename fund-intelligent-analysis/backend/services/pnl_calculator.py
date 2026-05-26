"""
盈亏计算服务
"""
from sqlalchemy.orm import joinedload
from loguru import logger

from backend.database import SessionLocal
from backend.models.holding import Holding


def calculate_pnl() -> None:
    """重算所有活跃持仓的盈亏"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
        count = 0

        for h in holdings:
            fund = h.fund
            if fund and fund.latest_nav:
                h.current_nav = fund.latest_nav

            # 重算市值
            h.current_value = float(h.shares or 0) * float(h.current_nav or 0)

            # 重算盈亏
            cost = float(h.cost_amount or 0)
            value = float(h.current_value or 0)
            h.pnl_amount = value - cost
            h.pnl_ratio = (value - cost) / cost * 100 if cost > 0 else 0

            count += 1

        db.commit()
        logger.info(f"盈亏计算完成，更新 {count} 条持仓")

    except Exception as e:
        logger.error(f"盈亏计算失败: {e}")
    finally:
        db.close()
