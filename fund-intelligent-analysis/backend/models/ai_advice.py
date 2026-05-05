from sqlalchemy import Column, Integer, String, Text, Boolean, Date, Time, DateTime, JSON, func
from backend.database import Base
import json


class AiAdvice(Base):
    __tablename__ = "ai_advices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    advice_date = Column(Date, nullable=False)
    advice_time = Column(Time, nullable=True)
    market_summary = Column(Text, default="")  # AI收到的行情摘要
    portfolio_snapshot = Column(Text, default="")  # AI收到的持仓快照JSON
    advice_content = Column(Text, default="")  # AI给出的完整建议文本
    actions = Column(JSON, default=list)  # 结构化操作建议列表
    market_view = Column(String(20), default="neutral")  # bullish/neutral/bearish
    overall_suggestion = Column(Text, default="")  # 总体建议
    risk_level = Column(String(20), default="medium")  # low/medium/high
    data_quality = Column(JSON, default=dict)  # 行情/新闻/持仓数据新鲜度
    reasoning = Column(Text, default="")  # AI推理过程
    model_name = Column(String(50), default="deepseek-chat")
    token_usage = Column(Integer, default=0)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        market_view = self.market_view or "neutral"
        overall_suggestion = self.overall_suggestion or ""
        risk_level = self.risk_level or "medium"
        opportunities = []
        if self.advice_content and (not overall_suggestion or market_view == "neutral"):
            try:
                parsed = json.loads(self.advice_content)
                overall_suggestion = overall_suggestion or parsed.get("overall_suggestion", "")
                risk_level = risk_level or parsed.get("risk_level", "medium")
                opportunities = parsed.get("opportunities", []) if isinstance(parsed.get("opportunities", []), list) else []
                legacy_view = parsed.get("market_view", "")
                if legacy_view in ("看多", "偏多", "bullish"):
                    market_view = "bullish"
                elif legacy_view in ("看空", "偏空", "bearish"):
                    market_view = "bearish"
            except Exception:
                pass
        elif self.advice_content:
            try:
                parsed = json.loads(self.advice_content)
                opportunities = parsed.get("opportunities", []) if isinstance(parsed.get("opportunities", []), list) else []
            except Exception:
                pass
        return {
            "id": self.id,
            "advice_date": str(self.advice_date) if self.advice_date else None,
            "advice_time": str(self.advice_time) if self.advice_time else None,
            "market_summary": self.market_summary,
            "portfolio_snapshot": self.portfolio_snapshot,
            "advice_content": self.advice_content,
            "actions": self.actions if self.actions else [],
            "opportunities": opportunities,
            "market_view": market_view,
            "overall_suggestion": overall_suggestion,
            "risk_level": risk_level,
            "data_quality": self.data_quality if self.data_quality else {},
            "reasoning": self.reasoning,
            "model_name": self.model_name,
            "token_usage": self.token_usage,
            "is_read": self.is_read,
        }
