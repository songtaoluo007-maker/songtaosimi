from sqlalchemy import Column, Integer, String, Numeric, BigInteger, Date, Time, DateTime, Index, func
from backend.database import Base


MOJIBAKE_MARKERS = ("æ", "ç", "è", "é", "å", "ä", "ï¼", "ã")


def repair_mojibake(value: str) -> str:
    if not isinstance(value, str) or not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value
    try:
        fixed = value.encode("latin1").decode("utf-8")
        return fixed or value
    except Exception:
        return value


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("ix_snapshot_symbol_date_type", "symbol", "snapshot_date", "snapshot_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)  # 如 000001.SH / SPX / fund_110011
    name = Column(String(50), nullable=False)
    snapshot_type = Column(String(10), nullable=False)  # index/sector/fund/global
    price = Column(Numeric(12, 4), default=0)  # 最新价/点位
    change_pct = Column(Numeric(8, 4), default=0)  # 涨跌幅%
    change_amount = Column(Numeric(12, 4), default=0)  # 涨跌额
    volume = Column(BigInteger, default=0)  # 成交量
    turnover = Column(Numeric(18, 2), default=0)  # 成交额
    high = Column(Numeric(12, 4), default=0)
    low = Column(Numeric(12, 4), default=0)
    open = Column(Numeric(12, 4), default=0)
    prev_close = Column(Numeric(12, 4), default=0)
    snapshot_date = Column(Date, nullable=False)
    snapshot_time = Column(Time, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": repair_mojibake(self.name),
            "snapshot_type": self.snapshot_type,
            "price": float(self.price) if self.price else 0,
            "change_pct": float(self.change_pct) if self.change_pct else 0,
            "change_amount": float(self.change_amount) if self.change_amount else 0,
            "volume": int(self.volume) if self.volume else 0,
            "turnover": float(self.turnover) if self.turnover else 0,
            "high": float(self.high) if self.high else 0,
            "low": float(self.low) if self.low else 0,
            "open": float(self.open) if self.open else 0,
            "prev_close": float(self.prev_close) if self.prev_close else 0,
            "snapshot_date": str(self.snapshot_date) if self.snapshot_date else None,
            "snapshot_time": str(self.snapshot_time) if self.snapshot_time else None,
        }
