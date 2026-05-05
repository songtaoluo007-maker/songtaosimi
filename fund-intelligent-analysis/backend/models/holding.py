from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(6), ForeignKey("funds.fund_code"), nullable=False, index=True)
    shares = Column(Numeric(16, 2), default=0)  # 持有份额
    cost_price = Column(Numeric(8, 4), default=0)  # 成本单价
    cost_amount = Column(Numeric(16, 2), default=0)  # 投入总成本
    current_nav = Column(Numeric(8, 4), default=0)  # 当前净值
    current_value = Column(Numeric(16, 2), default=0)  # 当前市值
    daily_pnl = Column(Numeric(16, 2), default=0)  # 当日盈亏
    daily_pnl_ratio = Column(Numeric(8, 4), default=0)  # 当日盈亏比例
    daily_pnl_date = Column(Date, nullable=True)  # 当日盈亏对应日期
    pnl_amount = Column(Numeric(16, 2), default=0)  # 浮动盈亏金额
    pnl_ratio = Column(Numeric(8, 4), default=0)  # 浮动盈亏比例
    source = Column(String(20), default="manual")  # manual/ocr_alipay/ocr_tiantian
    is_active = Column(Boolean, default=True)  # 是否持有中
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    fund = relationship("Fund", back_populates="holdings")

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "shares": float(self.shares) if self.shares is not None else 0.0,
            "cost_price": float(self.cost_price) if self.cost_price is not None else 0.0,
            "cost_amount": float(self.cost_amount) if self.cost_amount is not None else 0.0,
            "current_nav": float(self.current_nav) if self.current_nav is not None else 0.0,
            "current_value": float(self.current_value) if self.current_value is not None else 0.0,
            "daily_pnl": float(self.daily_pnl) if self.daily_pnl is not None else 0.0,
            "daily_pnl_ratio": float(self.daily_pnl_ratio) if self.daily_pnl_ratio is not None else 0.0,
            "daily_pnl_date": self.daily_pnl_date.isoformat() if self.daily_pnl_date else "",
            "pnl_amount": float(self.pnl_amount) if self.pnl_amount is not None else 0.0,
            "pnl_ratio": float(self.pnl_ratio) if self.pnl_ratio is not None else 0.0,
            "source": self.source or "manual",
            "is_active": self.is_active,
            "fund_name": self.fund.fund_name if self.fund else "",
            "fund_type": self.fund.fund_type if self.fund else "",
        }
