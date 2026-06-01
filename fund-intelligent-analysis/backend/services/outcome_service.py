"""
P3.2 建议结果追踪服务
到达复盘窗口后自动评估建议表现。
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from backend.models.ai_advice_memory import AiAdviceMemory
from backend.models.ai_advice_outcome import AiAdviceOutcome


class OutcomeService:
    REVIEW_HORIZONS = [1, 7, 30, 90]

    def __init__(self, db: Session):
        self.db = db

    def run_review(self) -> dict:
        """运行复盘任务：检查所有到期的记忆并生成 outcome"""
        today = datetime.now().date()
        created = 0
        skipped = 0
        errors = []

        memories = self.db.query(AiAdviceMemory).all()
        for memory in memories:
            memory_date = memory.created_at.date() if memory.created_at else today
            for horizon in self.REVIEW_HORIZONS:
                review_date = memory_date + timedelta(days=horizon)
                if review_date > today:
                    continue  # 还没到期

                # 检查是否已生成
                existing = self.db.query(AiAdviceOutcome).filter(
                    and_(
                        AiAdviceOutcome.memory_id == memory.id,
                        AiAdviceOutcome.review_horizon == horizon,
                    )
                ).first()
                if existing:
                    skipped += 1
                    continue

                try:
                    outcome = self._evaluate_memory(memory, horizon, str(review_date))
                    self.db.add(outcome)
                    created += 1
                except Exception as e:
                    errors.append(f"memory={memory.id} horizon={horizon}d: {str(e)}")

        self.db.commit()
        return {
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    def _evaluate_memory(
        self,
        memory: AiAdviceMemory,
        horizon: int,
        review_date: str,
    ) -> AiAdviceOutcome:
        """评估单条记忆在指定窗口的表现"""
        # TODO: 从行情服务获取实际收益数据
        # 当前先用占位逻辑，后续对接真实数据
        portfolio = memory.portfolio_snapshot or {}
        advice_json = memory.advice_json or {}

        # 基于建议决策的简单评分
        decision = memory.decision or "hold"
        confidence = memory.confidence or 0.5

        # 方向判断评分（占位：hold 得中分，add/reduce 看市场）
        direction_score = 50.0
        if decision == "hold":
            direction_score = 60.0  # 持有一般不会太差

        # 综合评分
        score = direction_score * 0.3 + confidence * 100 * 0.3 + 40 * 0.4

        return AiAdviceOutcome(
            memory_id=memory.id,
            review_horizon=horizon,
            review_date=review_date,
            portfolio_return=0.0,  # 待接入真实数据
            benchmark_return=0.0,
            target_fund_return=0.0,
            max_drawdown=0.0,
            volatility=0.0,
            would_have_helped="unknown",
            score=min(100, max(0, score)),
            outcome_summary=f"{horizon}天复盘：建议'{decision}'，置信度{confidence:.0%}",
            direction_correct=direction_score,
            drawdown_reduced=50.0,
            beat_hold=50.0,
            beat_benchmark=50.0,
            risk_appropriate=60.0,
            error_reason="",
        )

    def get_outcomes(
        self,
        memory_id: int = None,
        limit: int = 50,
    ) -> list[dict]:
        """查询复盘结果"""
        query = self.db.query(AiAdviceOutcome)
        if memory_id:
            query = query.filter(AiAdviceOutcome.memory_id == memory_id)
        query = query.order_by(AiAdviceOutcome.created_at.desc())
        results = query.limit(limit).all()
        return [o.to_dict() for o in results]

    def get_summary(self) -> dict:
        """获取复盘统计摘要"""
        total = self.db.query(AiAdviceOutcome).count()
        if total == 0:
            return {"total": 0, "avg_score": 0, "by_horizon": {}}

        outcomes = self.db.query(AiAdviceOutcome).all()
        avg_score = sum(o.score for o in outcomes) / total if total > 0 else 0

        by_horizon = {}
        for h in self.REVIEW_HORIZONS:
            h_outcomes = [o for o in outcomes if o.review_horizon == h]
            by_horizon[f"{h}d"] = {
                "count": len(h_outcomes),
                "avg_score": sum(o.score for o in h_outcomes) / len(h_outcomes) if h_outcomes else 0,
            }

        return {
            "total": total,
            "avg_score": round(avg_score, 1),
            "by_horizon": by_horizon,
        }
