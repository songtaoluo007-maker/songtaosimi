"""
P3.1 AI 建议记忆库
每次 AI 生成建议时保存完整上下文快照，支持复盘和检索。
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, JSON, func
from backend.database import Base


class AiAdviceMemory(Base):
    __tablename__ = "ai_advice_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now())

    # 建议元数据
    advice_type = Column(String(30), default="tail")  # tail/review/manual
    model_name = Column(String(50), default="deepseek-chat")
    prompt_version = Column(String(20), default="v1")

    # 上下文快照（生成建议时的完整状态）
    user_profile_snapshot = Column(JSON, default=dict)
    ai_profile_snapshot = Column(JSON, default=dict)
    portfolio_snapshot = Column(JSON, default=dict)
    market_context_snapshot = Column(JSON, default=dict)
    risk_context_snapshot = Column(JSON, default=dict)
    news_context_snapshot = Column(JSON, default=list)
    similar_cases_snapshot = Column(JSON, default=list)

    # AI 输出
    advice_json = Column(JSON, default=dict)  # 结构化建议
    advice_text = Column(Text, default="")  # 自然语言建议
    confidence = Column(Float, default=0.5)
    horizon_days = Column(Integer, default=30)
    decision = Column(String(20), default="hold")  # hold/add/reduce/buy/avoid

    # 操作详情
    action_type = Column(String(30), default="hold")
    target_funds = Column(JSON, default=list)  # ["000001", "110011"]
    reason_tags = Column(JSON, default=list)  # ["行业集中", "估值偏高"]

    # 用户反馈
    is_user_accepted = Column(Boolean, nullable=True)  # None=未反馈
    user_feedback = Column(Text, default="")
    feedback_tags = Column(JSON, default=list)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": str(self.created_at) if self.created_at else None,
            "advice_type": self.advice_type,
            "model_name": self.model_name,
            "confidence": self.confidence,
            "horizon_days": self.horizon_days,
            "decision": self.decision,
            "action_type": self.action_type,
            "target_funds": self.target_funds or [],
            "reason_tags": self.reason_tags or [],
            "is_user_accepted": self.is_user_accepted,
            "user_feedback": self.user_feedback or "",
            "feedback_tags": self.feedback_tags or [],
            "advice_json": self.advice_json or {},
            "advice_text": self.advice_text or "",
        }

    def to_summary(self):
        """轻量摘要，用于列表展示"""
        return {
            "id": self.id,
            "created_at": str(self.created_at) if self.created_at else None,
            "decision": self.decision,
            "confidence": self.confidence,
            "horizon_days": self.horizon_days,
            "action_type": self.action_type,
            "reason_tags": self.reason_tags or [],
            "is_user_accepted": self.is_user_accepted,
        }
