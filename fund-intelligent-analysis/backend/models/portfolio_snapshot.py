from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from backend.database import Base


class PortfolioDailySnapshot(Base):
    __tablename__ = "portfolio_daily_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", name="uq_portfolio_daily_snapshot_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    total_value = Column(Numeric(16, 2), nullable=False, default=0)
    total_cost = Column(Numeric(16, 2), nullable=False, default=0)
    total_pnl = Column(Numeric(16, 2), nullable=False, default=0)
    cash_flow = Column(Numeric(16, 2), default=0)
    note = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "snapshot_date": self.snapshot_date.isoformat() if self.snapshot_date else None,
            "total_value": float(self.total_value or 0),
            "total_cost": float(self.total_cost or 0),
            "total_pnl": float(self.total_pnl or 0),
            "cash_flow": float(self.cash_flow or 0),
            "note": self.note or "",
            "created_at": str(self.created_at) if self.created_at else None,
        }


class FundBenchmark(Base):
    __tablename__ = "fund_benchmarks"
    __table_args__ = (UniqueConstraint("fund_code", "benchmark_symbol", name="uq_fund_benchmark_symbol"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False, index=True)
    benchmark_symbol = Column(String(20), nullable=False, default="000300.SH")
    benchmark_name = Column(String(60), default="沪深300")
    benchmark_type = Column(String(20), default="broad")
    is_primary = Column(Boolean, default=True)
    auto_match = Column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "benchmark_symbol": self.benchmark_symbol,
            "benchmark_name": self.benchmark_name,
            "benchmark_type": self.benchmark_type,
            "is_primary": bool(self.is_primary),
            "auto_match": bool(self.auto_match),
        }
