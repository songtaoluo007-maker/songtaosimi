"""机构/主力/大户资金流向数据模型"""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Index, func
from backend.database import Base


class CapitalFlow(Base):
    __tablename__ = "capital_flows"
    __table_args__ = (
        Index("idx_capital_flow_date_type", "flow_date", "flow_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    flow_date = Column(Date, nullable=False, index=True)
    flow_type = Column(String(20), nullable=False, index=True)  # north_bound / main_force / margin / block_trade
    symbol = Column(String(20), default="")  # 市场/板块/个股代码，空=全市场
    name = Column(String(80), default="")

    # 通用资金指标
    net_inflow = Column(Numeric(18, 2), default=0)      # 净流入（亿元）
    buy_amount = Column(Numeric(18, 2), default=0)       # 买入额
    sell_amount = Column(Numeric(18, 2), default=0)      # 卖出额

    # 主力资金专用
    super_large_net = Column(Numeric(18, 2), default=0)  # 超大单净额
    large_net = Column(Numeric(18, 2), default=0)        # 大单净额
    medium_net = Column(Numeric(18, 2), default=0)       # 中单净额
    small_net = Column(Numeric(18, 2), default=0)        # 小单净额

    # 融资融券专用
    margin_balance = Column(Numeric(18, 2), default=0)   # 融资余额
    short_balance = Column(Numeric(18, 2), default=0)    # 融券余额

    # 龙虎榜专用
    institution_buy = Column(Numeric(18, 2), default=0)  # 机构买入
    institution_sell = Column(Numeric(18, 2), default=0) # 机构卖出

    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "flow_date": str(self.flow_date),
            "flow_type": self.flow_type,
            "symbol": self.symbol,
            "name": self.name,
            "net_inflow": float(self.net_inflow or 0),
            "buy_amount": float(self.buy_amount or 0),
            "sell_amount": float(self.sell_amount or 0),
            "super_large_net": float(self.super_large_net or 0),
            "large_net": float(self.large_net or 0),
            "medium_net": float(self.medium_net or 0),
            "small_net": float(self.small_net or 0),
            "margin_balance": float(self.margin_balance or 0),
            "short_balance": float(self.short_balance or 0),
            "institution_buy": float(self.institution_buy or 0),
            "institution_sell": float(self.institution_sell or 0),
        }
