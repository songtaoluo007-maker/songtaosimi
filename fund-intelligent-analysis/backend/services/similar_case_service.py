"""
P3.4 相似历史场景检索
基于 SQLite 结构化相似度，不引入向量数据库。
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.models.ai_advice_memory import AiAdviceMemory
from backend.models.ai_advice_outcome import AiAdviceOutcome


class SimilarCaseService:
    """相似案例检索：根据多维度匹配历史场景"""

    def __init__(self, db: Session):
        self.db = db

    def find_similar(
        self,
        market_trend: str = "neutral",  # up/down/neutral
        fund_type: str = "mixed",  # stock/bond/mixed/index
        current_drawdown: float = 0.0,
        sector_concentration: float = 0.5,
        risk_level: str = "medium",
        limit: int = 5,
    ) -> list[dict]:
        """查找相似历史案例"""
        memories = self.db.query(AiAdviceMemory).order_by(
            desc(AiAdviceMemory.created_at)
        ).limit(200).all()

        scored = []
        for m in memories:
            score = self._calc_similarity(
                m, market_trend, fund_type, current_drawdown,
                sector_concentration, risk_level
            )
            if score > 0.2:  # 最低相似度阈值
                scored.append((m, score))

        # 按相似度排序
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for m, sim_score in scored[:limit]:
            # 获取该记忆的复盘结果
            outcomes = self.db.query(AiAdviceOutcome).filter(
                AiAdviceOutcome.memory_id == m.id
            ).all()

            results.append({
                "memory_id": m.id,
                "created_at": str(m.created_at) if m.created_at else None,
                "decision": m.decision,
                "confidence": m.confidence,
                "reason_tags": m.reason_tags or [],
                "similarity_score": round(sim_score, 3),
                "advice_summary": (m.advice_text or "")[:200],
                "is_user_accepted": m.is_user_accepted,
                "outcomes": [
                    {
                        "horizon": o.review_horizon,
                        "score": o.score,
                        "would_have_helped": o.would_have_helped,
                    }
                    for o in outcomes
                ],
            })

        return results

    def _calc_similarity(
        self,
        memory: AiAdviceMemory,
        market_trend: str,
        fund_type: str,
        current_drawdown: float,
        sector_concentration: float,
        risk_level: str,
    ) -> float:
        """计算相似度得分（0-1）"""
        score = 0.0
        weights = {
            "market_trend": 0.25,
            "risk_level": 0.20,
            "decision_match": 0.20,
            "portfolio_match": 0.15,
            "time_decay": 0.20,
        }

        # 1. 市场趋势匹配
        m_market = (memory.market_context_snapshot or {}).get("trend", "neutral")
        if m_market == market_trend:
            score += weights["market_trend"]

        # 2. 风险等级匹配
        m_risk = memory.risk_context_snapshot.get("level", "medium") if memory.risk_context_snapshot else "medium"
        if m_risk == risk_level:
            score += weights["risk_level"]

        # 3. 建议决策匹配（相似场景通常给出相似建议）
        # 这里不加权，因为我们要找的是"相似场景下的不同决策"也有参考价值

        # 4. 组合特征匹配
        m_portfolio = memory.portfolio_snapshot or {}
        m_concentration = m_portfolio.get("sector_concentration", 0.5)
        if abs(m_concentration - sector_concentration) < 0.2:
            score += weights["portfolio_match"]

        # 5. 时间衰减（越近越相关）
        if memory.created_at:
            from datetime import datetime
            days_ago = (datetime.now() - memory.created_at).days
            time_weight = max(0, 1 - days_ago / 365)
            score += weights["time_decay"] * time_weight

        return score

    def get_case_for_prompt(self, case: dict) -> str:
        """将案例压缩为可注入 prompt 的文本"""
        outcomes_text = ""
        if case.get("outcomes"):
            parts = []
            for o in case["outcomes"]:
                parts.append(f"{o['horizon']}d评分{o['score']:.0f}")
            outcomes_text = f"复盘: {', '.join(parts)}"

        accepted = "采纳" if case.get("is_user_accepted") else (
            "未采纳" if case.get("is_user_accepted") is False else "未知"
        )

        return (
            f"[历史案例 {case['created_at']}] "
            f"决策: {case['decision']} (置信度 {case['confidence']:.0%}), "
            f"用户{accepted}. "
            f"理由: {', '.join(case.get('reason_tags', []))}. "
            f"{outcomes_text}"
        )
