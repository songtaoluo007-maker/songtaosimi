"""
盈亏计算服务
"""
from datetime import date
from loguru import logger

from backend.database import SessionLocal
from backend.models.holding import Holding
from backend.models.fund import Fund


def calculate_pnl():
    """重算所有活跃持仓的盈亏"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).filter(Holding.is_active == True).all()
        count = 0

        for h in holdings:
            # 获取最新净值
            fund = db.query(Fund).filter(Fund.fund_code == h.fund_code).first()
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
