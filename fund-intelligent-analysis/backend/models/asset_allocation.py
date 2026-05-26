"""
目标资产配置 + 再平衡预警 — P1.2

老基民纪律工具：设定 60% 股 / 30% 债 / 10% 黄金，
偏离 > tolerance 时提醒再平衡。

asset_class 取值（与 `_classify_fund_to_asset_class` 一致）：
- 'equity_a'    A 股权益
- 'equity_hk'   港股权益
- 'equity_us'   美股/海外权益（QDII）
- 'bond'        债券
- 'gold'        黄金/贵金属
- 'cash'        货币/现金
"""
from sqlalchemy import Boolean, Column, Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func

from backend.database import Base


class AssetAllocationTarget(Base):
    __tablename__ = "asset_allocation_targets"
    __table_args__ = (
        UniqueConstraint("asset_class", name="uq_aat_class"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_class = Column(String(20), nullable=False)
    target_pct = Column(Numeric(5, 2), nullable=False)
    tolerance_pct = Column(Numeric(4, 2), nullable=False, default=5.0)
    notes = Column(String(200), default="")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "asset_class": self.asset_class,
            "target_pct": float(self.target_pct or 0),
            "tolerance_pct": float(self.tolerance_pct or 5),
            "notes": self.notes or "",
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }


class RebalanceAlert(Base):
    __tablename__ = "rebalance_alerts"
    __table_args__ = (
        Index("idx_ra_unack", "is_acknowledged", "detect_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    detect_date = Column(Date, nullable=False)
    asset_class = Column(String(20), nullable=False)
    target_pct = Column(Numeric(5, 2))
    current_pct = Column(Numeric(5, 2))
    deviation_pct = Column(Numeric(5, 2))
    suggested_action = Column(String(10))  # 'add' | 'reduce'
    suggested_amount = Column(Numeric(14, 2))
    is_acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "detect_date": self.detect_date.isoformat() if self.detect_date else None,
            "asset_class": self.asset_class,
            "target_pct": float(self.target_pct or 0),
            "current_pct": float(self.current_pct or 0),
            "deviation_pct": float(self.deviation_pct or 0),
            "suggested_action": self.suggested_action,
            "suggested_amount": float(self.suggested_amount or 0),
            "is_acknowledged": bool(self.is_acknowledged),
            "created_at": str(self.created_at) if self.created_at else None,
        }
