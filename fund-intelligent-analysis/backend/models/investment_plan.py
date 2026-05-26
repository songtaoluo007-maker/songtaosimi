"""
定投计划 + 执行记录 — P1.1

老基民经典需求：大部分人的真实操作是定投而非一次买入。系统按定投建模才能：
- 看到累计已投/期数进度
- 看到摊薄成本（cumulative_cost / cumulative_shares）
- 画出微笑曲线（NAV 折线 + 每期定投点）

plan_type 取值：
- 'daily'    每个交易日
- 'weekly'   每周 N（day_of_period: 0=周一 ... 4=周五）
- 'biweekly' 每两周（同 weekly 算法 + 起始日奇偶判断）
- 'monthly'  每月 N 日（day_of_period: 1-28）
"""
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from backend.database import Base


class InvestmentPlan(Base):
    __tablename__ = "investment_plans"
    __table_args__ = (
        Index("idx_ip_active_fund", "is_active", "fund_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False)
    plan_name = Column(String(60), default="")
    plan_type = Column(String(10), nullable=False)  # daily / weekly / biweekly / monthly
    amount = Column(Numeric(12, 2), nullable=False)
    day_of_period = Column(Integer)  # monthly=1-28; weekly=0-6（周一=0）
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    target_amount = Column(Numeric(14, 2))
    is_active = Column(Boolean, default=True)
    auto_execute = Column(Boolean, default=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    executions = relationship(
        "InvestmentPlanExecution",
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "plan_name": self.plan_name or "",
            "plan_type": self.plan_type,
            "amount": float(self.amount or 0),
            "day_of_period": self.day_of_period,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "target_amount": float(self.target_amount or 0) if self.target_amount else None,
            "is_active": bool(self.is_active),
            "auto_execute": bool(self.auto_execute),
            "notes": self.notes or "",
            "created_at": str(self.created_at) if self.created_at else None,
        }


class InvestmentPlanExecution(Base):
    __tablename__ = "investment_plan_executions"
    __table_args__ = (
        UniqueConstraint("plan_id", "scheduled_date", name="uq_ipe_plan_date"),
        Index("idx_ipe_due", "executed", "scheduled_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("investment_plans.id"), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    executed = Column(Boolean, default=False)
    executed_at = Column(DateTime)
    trade_id = Column(Integer)  # 关联 trades.id（非强制外键，避免误删交易时连锁）
    actual_amount = Column(Numeric(12, 2))
    actual_shares = Column(Numeric(16, 4))
    nav_price = Column(Numeric(10, 4))
    skip_reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    plan = relationship("InvestmentPlan", back_populates="executions")

    def to_dict(self):
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "executed": bool(self.executed),
            "executed_at": str(self.executed_at) if self.executed_at else None,
            "trade_id": self.trade_id,
            "actual_amount": float(self.actual_amount or 0),
            "actual_shares": float(self.actual_shares or 0),
            "nav_price": float(self.nav_price or 0),
            "skip_reason": self.skip_reason or "",
        }
