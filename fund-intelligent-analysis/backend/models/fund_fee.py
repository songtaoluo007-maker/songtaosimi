"""
基金费率 + 每日计提账本 — P2.1

老基民血泪经验：10 年下来管理费 1.5%/年 × 10 年 ≈ 吃掉 14% 收益。
本模块让"长期被扣的真实成本"可见 + 实时算赎回费预估。

费率字段说明（全部为小数，例如 0.015 = 1.5%）：
- purchase_fee_rate: 申购费率（基础）
- purchase_fee_discount: 折扣（如天天基金常 0.1 = 1 折）
- redemption_fee_schedule: JSON 数组 [{min_days, max_days, rate}, ...]
- management_fee_rate / custody_fee_rate / sales_service_fee_rate: 年费率
"""
from sqlalchemy import (
    Column, Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, func,
)

from backend.database import Base


class FundFeeSchedule(Base):
    __tablename__ = "fund_fee_schedules"
    __table_args__ = (
        UniqueConstraint("fund_code", name="uq_ffs_fund"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False, index=True)
    purchase_fee_rate = Column(Numeric(7, 5), default=0)
    purchase_fee_discount = Column(Numeric(4, 3), default=0.1)
    redemption_fee_schedule = Column(Text, default="")  # JSON 数组字符串
    management_fee_rate = Column(Numeric(7, 5), default=0)
    custody_fee_rate = Column(Numeric(7, 5), default=0)
    sales_service_fee_rate = Column(Numeric(7, 5), default=0)
    source = Column(String(20), default="manual")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        import json
        try:
            redemption = json.loads(self.redemption_fee_schedule) if self.redemption_fee_schedule else []
        except Exception:
            redemption = []
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "purchase_fee_rate": float(self.purchase_fee_rate or 0),
            "purchase_fee_discount": float(self.purchase_fee_discount or 0.1),
            "redemption_fee_schedule": redemption,
            "management_fee_rate": float(self.management_fee_rate or 0),
            "custody_fee_rate": float(self.custody_fee_rate or 0),
            "sales_service_fee_rate": float(self.sales_service_fee_rate or 0),
            "source": self.source or "manual",
        }


class FeeDailyAccrual(Base):
    __tablename__ = "fee_daily_accruals"
    __table_args__ = (
        UniqueConstraint("accrual_date", "fund_code", name="uq_fda_date_fund"),
        Index("idx_fda_date", "accrual_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    accrual_date = Column(Date, nullable=False)
    fund_code = Column(String(10), nullable=False)
    holding_value = Column(Numeric(16, 2), default=0)
    daily_mgmt_fee = Column(Numeric(12, 4), default=0)
    daily_custody_fee = Column(Numeric(12, 4), default=0)
    daily_sales_fee = Column(Numeric(12, 4), default=0)
    created_at = Column(DateTime, server_default=func.now())

    @property
    def daily_total_fee(self) -> float:
        return float(self.daily_mgmt_fee or 0) + float(self.daily_custody_fee or 0) + float(self.daily_sales_fee or 0)

    def to_dict(self):
        return {
            "id": self.id,
            "accrual_date": self.accrual_date.isoformat() if self.accrual_date else None,
            "fund_code": self.fund_code,
            "holding_value": float(self.holding_value or 0),
            "daily_mgmt_fee": float(self.daily_mgmt_fee or 0),
            "daily_custody_fee": float(self.daily_custody_fee or 0),
            "daily_sales_fee": float(self.daily_sales_fee or 0),
            "daily_total_fee": self.daily_total_fee,
        }
