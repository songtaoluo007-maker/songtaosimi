"""
P3.2 建议结果追踪器
到达复盘窗口后自动评估建议表现。
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, func, UniqueConstraint
from backend.database import Base


class AiAdviceOutcome(Base):
    __tablename__ = "ai_advice_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # 复盘参数
    review_horizon = Column(Integer, nullable=False)  # 1/7/30/90 天
    review_date = Column(String(10), nullable=False)  # YYYY-MM-DD

    # 表现数据
    portfolio_return = Column(Float, default=0.0)  # 组合收益率
    benchmark_return = Column(Float, default=0.0)  # 基准收益率（沪深300）
    target_fund_return = Column(Float, default=0.0)  # 目标基金收益率
    max_drawdown = Column(Float, default=0.0)  # 最大回撤
    volatility = Column(Float, default=0.0)  # 波动率

    # 评分
    would_have_helped = Column(String(20), default="unknown")  # yes/no/unknown
    score = Column(Float, default=0.0)  # 0-100 综合评分
    outcome_summary = Column(Text, default="")  # 复盘摘要

    # 维度评分
    direction_correct = Column(Float, default=0.0)  # 方向判断正确度
    drawdown_reduced = Column(Float, default=0.0)  # 是否降低回撤
    beat_hold = Column(Float, default=0.0)  # 是否优于持有不动
    beat_benchmark = Column(Float, default=0.0)  # 是否优于基准
    risk_appropriate = Column(Float, default=0.0)  # 是否符合风险偏好

    # 错误处理
    error_reason = Column(String(200), default="")

    __table_args__ = (
        UniqueConstraint("memory_id", "review_horizon", name="uq_memory_horizon"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "memory_id": self.memory_id,
            "created_at": str(self.created_at) if self.created_at else None,
            "review_horizon": self.review_horizon,
            "review_date": self.review_date,
            "portfolio_return": self.portfolio_return,
            "benchmark_return": self.benchmark_return,
            "target_fund_return": self.target_fund_return,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "would_have_helped": self.would_have_helped,
            "score": self.score,
            "outcome_summary": self.outcome_summary or "",
            "direction_correct": self.direction_correct,
            "drawdown_reduced": self.drawdown_reduced,
            "beat_hold": self.beat_hold,
            "beat_benchmark": self.beat_benchmark,
            "risk_appropriate": self.risk_appropriate,
            "error_reason": self.error_reason or "",
        }
