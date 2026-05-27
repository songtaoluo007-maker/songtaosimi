"""
用户决策复盘 — P2.2

老基民价值最高的功能：让用户看见自己的"人性弱点模式"
- 跟 AI 建议 vs 反着做，30 天后回测胜率
- 高位加仓 / 低位减仓 / 频繁交易 等典型反人性行为统计

记录两种数据：
1. UserDecisionReview — 单次操作的决策快照（决策日 + 30 天后的结果）
2. BehaviorBiasSnapshot — 月度行为偏差快照，用于雷达图
"""
from sqlalchemy import (
    Column, Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, func,
)

from backend.database import Base


class UserDecisionReview(Base):
    __tablename__ = "user_decision_reviews"
    __table_args__ = (
        Index("idx_udr_date", "decision_date"),
        Index("idx_udr_pending", "is_reviewed", "decision_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    advice_id = Column(Integer)  # 关联 ai_advices.id，可空（用户主动操作未跟建议）
    fund_code = Column(String(10))  # 可空（整体仓位决策）
    decision_date = Column(Date, nullable=False)
    user_action = Column(String(20))     # 'follow' / 'ignore' / 'reverse' / 'self'
    decision_type = Column(String(20))   # 'buy' / 'sell' / 'hold' / 'rebalance'
    decision_amount = Column(Numeric(14, 2))
    market_state_then = Column(String(20))   # bullish / bearish / neutral
    portfolio_value_then = Column(Numeric(16, 2))
    fund_nav_then = Column(Numeric(10, 4))

    # 30 天后回填
    portfolio_value_30d = Column(Numeric(16, 2))
    fund_nav_30d = Column(Numeric(10, 4))
    market_state_30d = Column(String(20))
    outcome = Column(String(20))   # 'win' / 'loss' / 'neutral'
    outcome_pct = Column(Numeric(6, 2))
    lesson = Column(Text)

    is_reviewed = Column(Integer, default=0)  # 0/1，整数兼容旧库
    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "advice_id": self.advice_id,
            "fund_code": self.fund_code or "",
            "decision_date": self.decision_date.isoformat() if self.decision_date else None,
            "user_action": self.user_action,
            "decision_type": self.decision_type,
            "decision_amount": float(self.decision_amount or 0),
            "market_state_then": self.market_state_then,
            "portfolio_value_then": float(self.portfolio_value_then or 0),
            "fund_nav_then": float(self.fund_nav_then or 0),
            "portfolio_value_30d": float(self.portfolio_value_30d or 0) if self.portfolio_value_30d else None,
            "fund_nav_30d": float(self.fund_nav_30d or 0) if self.fund_nav_30d else None,
            "market_state_30d": self.market_state_30d,
            "outcome": self.outcome,
            "outcome_pct": float(self.outcome_pct or 0),
            "lesson": self.lesson or "",
            "is_reviewed": bool(self.is_reviewed),
            "created_at": str(self.created_at) if self.created_at else None,
            "reviewed_at": str(self.reviewed_at) if self.reviewed_at else None,
        }


class BehaviorBiasSnapshot(Base):
    __tablename__ = "behavior_bias_snapshots"
    __table_args__ = (
        UniqueConstraint("month", name="uq_bbs_month"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String(7), nullable=False)  # 'YYYY-MM'
    chase_high_score = Column(Numeric(5, 2), default=0)        # 追涨：高位加仓次数 / 总加仓次数
    cut_low_score = Column(Numeric(5, 2), default=0)           # 杀跌
    frequent_trade_score = Column(Numeric(5, 2), default=0)    # 频繁交易
    avg_holding_days = Column(Numeric(8, 1), default=0)
    follow_advice_rate = Column(Numeric(5, 2), default=0)      # 跟随 AI 建议比例
    follow_win_rate = Column(Numeric(5, 2), default=0)         # 跟随建议的胜率
    reverse_win_rate = Column(Numeric(5, 2), default=0)        # 反着做的胜率
    self_win_rate = Column(Numeric(5, 2), default=0)           # 主动操作的胜率
    biggest_regret = Column(Text)                              # 当月最让你后悔的决策
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "month": self.month,
            "chase_high_score": float(self.chase_high_score or 0),
            "cut_low_score": float(self.cut_low_score or 0),
            "frequent_trade_score": float(self.frequent_trade_score or 0),
            "avg_holding_days": float(self.avg_holding_days or 0),
            "follow_advice_rate": float(self.follow_advice_rate or 0),
            "follow_win_rate": float(self.follow_win_rate or 0),
            "reverse_win_rate": float(self.reverse_win_rate or 0),
            "self_win_rate": float(self.self_win_rate or 0),
            "biggest_regret": self.biggest_regret or "",
            "created_at": str(self.created_at) if self.created_at else None,
        }
