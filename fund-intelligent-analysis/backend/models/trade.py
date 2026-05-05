from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from backend.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(6), ForeignKey("funds.fund_code"), nullable=False, index=True)
    trade_type = Column(String(4), nullable=False)  # 买入/卖出
    shares = Column(Numeric(16, 2), default=0)  # 交易份额
    nav_price = Column(Numeric(8, 4), default=0)  # 成交净值
    amount = Column(Numeric(16, 2), default=0)  # 成交金额
    fee = Column(Numeric(10, 2), default=0)  # 手续费
    trade_date = Column(Date, nullable=False)
    confirm_date = Column(Date, nullable=True)
    source = Column(String(20), default="manual")  # manual/ocr
    note = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())

    # 关系
    fund = relationship("Fund", back_populates="trades")

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "trade_type": self.trade_type,
            "shares": float(self.shares) if self.shares else 0,
            "nav_price": float(self.nav_price) if self.nav_price else 0,
            "amount": float(self.amount) if self.amount else 0,
            "fee": float(self.fee) if self.fee else 0,
            "trade_date": str(self.trade_date) if self.trade_date else None,
            "confirm_date": str(self.confirm_date) if self.confirm_date else None,
            "source": self.source,
            "note": self.note,
            "fund_name": self.fund.fund_name if self.fund else "",
        }
