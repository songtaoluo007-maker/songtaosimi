"""
基金经理 + 经理变更预警 ORM 模型 — P0.2

字段说明：
- FundManager: 一只基金的历任和现任基金经理
- ManagerAlert: 检测到的经理变更事件，分 high/medium/low 优先级
"""
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, func,
)

from backend.database import Base


class FundManager(Base):
    __tablename__ = "fund_managers"
    __table_args__ = (
        UniqueConstraint("fund_code", "manager_name", "start_date",
                         name="uq_fund_manager_start"),
        Index("idx_fm_current", "fund_code", "is_current"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False, index=True)
    manager_name = Column(String(60), nullable=False)
    manager_id = Column(String(40))  # 来源平台内部 ID（如东财），无则空
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)  # NULL = 现任
    tenure_return_pct = Column(Numeric(10, 2))  # 任职期间累计收益率
    tenure_annualized_pct = Column(Numeric(8, 2))  # 任职期间年化
    is_current = Column(Boolean, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "manager_name": self.manager_name,
            "manager_id": self.manager_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "tenure_return_pct": float(self.tenure_return_pct or 0),
            "tenure_annualized_pct": float(self.tenure_annualized_pct or 0),
            "is_current": bool(self.is_current),
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }


class ManagerAlert(Base):
    __tablename__ = "manager_alerts"
    __table_args__ = (
        Index("idx_ma_fund_unread", "fund_code", "is_read"),
        Index("idx_ma_severity", "severity", "alert_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False)
    alert_type = Column(String(40), nullable=False)
    # alert_type 取值：
    #  - 'departure'        现任经理离职
    #  - 'new_join'         新增基金经理
    #  - 'tenure_milestone' 任职满 1/3/5 年里程碑
    old_manager = Column(String(60))
    new_manager = Column(String(60))
    alert_date = Column(Date, nullable=False)
    is_read = Column(Boolean, default=False)
    severity = Column(String(10), default="medium")  # 'high' | 'medium' | 'low'
    detail = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "alert_type": self.alert_type,
            "old_manager": self.old_manager,
            "new_manager": self.new_manager,
            "alert_date": self.alert_date.isoformat() if self.alert_date else None,
            "is_read": bool(self.is_read),
            "severity": self.severity or "medium",
            "detail": self.detail or "",
            "created_at": str(self.created_at) if self.created_at else None,
        }
