"""
基金前十大持股快照 — P0.3

每季度从 AKShare `fund_portfolio_hold_em` 同步一次；
为持仓重叠度（overlap）计算提供底层数据。

关键索引：
- (fund_code, quarter) 唯一定位某基金某季度的全部持仓行
- stock_code 单独索引，用于反向查询"哪些基金重仓某只股票"
"""
from sqlalchemy import Column, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func

from backend.database import Base


class FundTopHolding(Base):
    __tablename__ = "fund_top_holdings"
    __table_args__ = (
        UniqueConstraint("fund_code", "stock_code", "quarter",
                         name="uq_fth_fund_stock_quarter"),
        Index("idx_fth_fund_quarter", "fund_code", "quarter"),
        Index("idx_fth_stock", "stock_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False)
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(60))
    weight_pct = Column(Numeric(6, 3))  # 占基金净值比例，0-100
    shares = Column(Numeric(20, 2))     # 持股数（股）
    market_value = Column(Numeric(20, 2))  # 持仓市值（元）
    quarter = Column(String(10), nullable=False)  # 如 '2025Q1' / '2025'
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name or "",
            "weight_pct": float(self.weight_pct or 0),
            "shares": float(self.shares or 0),
            "market_value": float(self.market_value or 0),
            "quarter": self.quarter,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }
