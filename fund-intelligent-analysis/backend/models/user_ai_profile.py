"""
P3.3 动态 AI 用户画像
AI 根据交易历史、反馈、建议结果推断的用户投资特征。
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, func
from backend.database import Base


class UserAiProfile(Base):
    __tablename__ = "user_ai_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 风险特征
    risk_tolerance_score = Column(Float, default=5.0)  # 1-10
    drawdown_sensitivity = Column(Float, default=5.0)  # 1-10，越高越敏感
    panic_sell_risk_score = Column(Float, default=3.0)  # 1-10，恐慌卖出倾向
    chasing_risk_score = Column(Float, default=3.0)  # 1-10，追高倾向

    # 交易偏好
    trade_frequency_preference = Column(String(20), default="low")  # low/medium/high
    preferred_holding_period = Column(String(20), default="medium")  # short/medium/long
    style_preference = Column(String(20), default="balanced")  # conservative/balanced/aggressive

    # 行为模式
    loss_reaction_pattern = Column(String(30), default="hold")  # hold/reduce/panic_sell
    confidence_adjustment = Column(Float, default=0.0)  # -1~1，建议置信度调整

    # 证据
    evidence_summary = Column(Text, default="")  # 最近一次更新的依据
    evidence_tags = Column(JSON, default=list)  # ["频繁卖出", "长期持有"]

    # 统计数据
    total_advices = Column(Integer, default=0)
    accepted_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    avg_outcome_score = Column(Float, default=0.0)

    def to_dict(self):
        return {
            "id": self.id,
            "updated_at": str(self.updated_at) if self.updated_at else None,
            "risk_tolerance_score": self.risk_tolerance_score,
            "drawdown_sensitivity": self.drawdown_sensitivity,
            "panic_sell_risk_score": self.panic_sell_risk_score,
            "chasing_risk_score": self.chasing_risk_score,
            "trade_frequency_preference": self.trade_frequency_preference,
            "preferred_holding_period": self.preferred_holding_period,
            "style_preference": self.style_preference,
            "loss_reaction_pattern": self.loss_reaction_pattern,
            "confidence_adjustment": self.confidence_adjustment,
            "evidence_summary": self.evidence_summary or "",
            "evidence_tags": self.evidence_tags or [],
            "total_advices": self.total_advices,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "avg_outcome_score": self.avg_outcome_score,
        }
