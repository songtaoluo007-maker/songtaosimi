"""
P3.1 AI 建议记忆服务
管理建议记忆的创建、查询、反馈。
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.ai_advice_memory import AiAdviceMemory


class MemoryService:
    def __init__(self, db: Session):
        self.db = db

    def create_memory(
        self,
        advice_type: str = "tail",
        model_name: str = "deepseek-chat",
        prompt_version: str = "v1",
        user_profile_snapshot: dict = None,
        ai_profile_snapshot: dict = None,
        portfolio_snapshot: dict = None,
        market_context_snapshot: dict = None,
        risk_context_snapshot: dict = None,
        news_context_snapshot: list = None,
        similar_cases_snapshot: list = None,
        advice_json: dict = None,
        advice_text: str = "",
        confidence: float = 0.5,
        horizon_days: int = 30,
        decision: str = "hold",
        action_type: str = "hold",
        target_funds: list = None,
        reason_tags: list = None,
    ) -> AiAdviceMemory:
        """创建一条建议记忆"""
        memory = AiAdviceMemory(
            advice_type=advice_type,
            model_name=model_name,
            prompt_version=prompt_version,
            user_profile_snapshot=user_profile_snapshot or {},
            ai_profile_snapshot=ai_profile_snapshot or {},
            portfolio_snapshot=portfolio_snapshot or {},
            market_context_snapshot=market_context_snapshot or {},
            risk_context_snapshot=risk_context_snapshot or {},
            news_context_snapshot=news_context_snapshot or [],
            similar_cases_snapshot=similar_cases_snapshot or [],
            advice_json=advice_json or {},
            advice_text=advice_text,
            confidence=confidence,
            horizon_days=horizon_days,
            decision=decision,
            action_type=action_type,
            target_funds=target_funds or [],
            reason_tags=reason_tags or [],
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def get_memories(
        self,
        limit: int = 50,
        offset: int = 0,
        decision: str = None,
        accepted: bool = None,
    ) -> list[dict]:
        """查询历史记忆"""
        query = self.db.query(AiAdviceMemory)
        if decision:
            query = query.filter(AiAdviceMemory.decision == decision)
        if accepted is not None:
            query = query.filter(AiAdviceMemory.is_user_accepted == accepted)
        query = query.order_by(AiAdviceMemory.created_at.desc())
        results = query.offset(offset).limit(limit).all()
        return [m.to_summary() for m in results]

    def get_memory(self, memory_id: int) -> Optional[dict]:
        """获取单条记忆详情"""
        m = self.db.query(AiAdviceMemory).filter(AiAdviceMemory.id == memory_id).first()
        return m.to_dict() if m else None

    def submit_feedback(
        self,
        memory_id: int,
        is_accepted: bool,
        feedback: str = "",
        feedback_tags: list = None,
    ) -> bool:
        """提交用户反馈"""
        m = self.db.query(AiAdviceMemory).filter(AiAdviceMemory.id == memory_id).first()
        if not m:
            return False
        m.is_user_accepted = is_accepted
        m.user_feedback = feedback
        m.feedback_tags = feedback_tags or []
        self.db.commit()
        return True

    def get_memory_for_prompt(self, memory_id: int) -> Optional[str]:
        """将记忆压缩为可注入 prompt 的文本"""
        m = self.db.query(AiAdviceMemory).filter(AiAdviceMemory.id == memory_id).first()
        if not m:
            return None
        advice = m.advice_json or {}
        return (
            f"日期: {m.created_at}\n"
            f"决策: {m.decision} (置信度 {m.confidence:.0%})\n"
            f"理由: {', '.join(m.reason_tags or [])}\n"
            f"操作: {m.action_type} → {', '.join(m.target_funds or [])}\n"
            f"用户采纳: {'是' if m.is_user_accepted else '否' if m.is_user_accepted is False else '未反馈'}\n"
            f"反馈: {m.user_feedback or '无'}"
        )

    def count_total(self) -> int:
        return self.db.query(AiAdviceMemory).count()

    def count_accepted(self) -> int:
        return self.db.query(AiAdviceMemory).filter(
            AiAdviceMemory.is_user_accepted == True
        ).count()

    def count_rejected(self) -> int:
        return self.db.query(AiAdviceMemory).filter(
            AiAdviceMemory.is_user_accepted == False
        ).count()
