from sqlalchemy import Column, Integer, String, Text, Date, Float, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from backend.database import Base


class AiAdviceReview(Base):
    """AI 建议复盘 — 跟踪每条建议的后续实际表现，计算命中率"""
    __tablename__ = "ai_advice_reviews"
    __table_args__ = (
        Index("idx_advice_review_advice_id", "advice_id"),
        Index("idx_advice_review_date", "review_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    advice_id = Column(Integer, ForeignKey("ai_advices.id"), nullable=False)
    review_date = Column(Date, nullable=False, comment="复盘日期")

    # 实际收益
    next_day_return = Column(Float, default=0, comment="次日组合收益 %")
    three_day_return = Column(Float, default=0, comment="3日组合收益 %")
    five_day_return = Column(Float, default=0, comment="5日组合收益 %")
    next_day_market_return = Column(Float, default=0, comment="次日沪深300收益 %")
    three_day_market_return = Column(Float, default=0, comment="3日沪深300收益 %")
    five_day_market_return = Column(Float, default=0, comment="5日沪深300收益 %")

    # 命中判定
    hit_result = Column(String(20), default="pending", comment="hit/miss/partial/pending")
    hit_score = Column(Float, default=0, comment="0-100 综合命中分")
    review_summary = Column(Text, default="", comment="复盘总结")
    error_reason = Column(Text, default="", comment="若miss/partial，偏差原因分析")

    created_at = Column(DateTime, server_default=func.now())

    advice = relationship("AiAdvice", backref="review", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "advice_id": self.advice_id,
            "review_date": str(self.review_date) if self.review_date else None,
            "next_day_return": self.next_day_return,
            "three_day_return": self.three_day_return,
            "five_day_return": self.five_day_return,
            "next_day_market_return": self.next_day_market_return,
            "three_day_market_return": self.three_day_market_return,
            "five_day_market_return": self.five_day_market_return,
            "hit_result": self.hit_result,
            "hit_score": self.hit_score,
            "review_summary": self.review_summary,
            "error_reason": self.error_reason,
        }
