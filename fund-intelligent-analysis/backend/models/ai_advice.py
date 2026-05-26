from sqlalchemy import Column, Integer, String, Text, Boolean, Date, Time, DateTime, JSON, Index, func
from backend.database import Base
import json


class AiAdvice(Base):
    __tablename__ = "ai_advices"
    __table_args__ = (
        Index("idx_ai_advices_date", "advice_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    advice_date = Column(Date, nullable=False)
    advice_time = Column(Time, nullable=True)
    market_summary = Column(Text, default="")  # AI收到的行情摘要(旧版，保留向后兼容)
    portfolio_snapshot = Column(Text, default="")  # AI收到的持仓快照JSON(旧版)
    advice_content = Column(Text, default="")  # AI给出的完整建议文本(旧版原始输出)
    actions = Column(JSON, default=list)  # 结构化操作建议列表
    market_view = Column(String(20), default="neutral")  # bullish/neutral/bearish
    overall_suggestion = Column(Text, default="")  # 总体建议
    risk_level = Column(String(20), default="medium")  # low/medium/high
    data_quality = Column(JSON, default=dict)  # 行情/新闻/持仓数据新鲜度
    reasoning = Column(Text, default="")  # AI推理过程
    model_name = Column(String(50), default="deepseek-chat")
    token_usage = Column(Integer, default=0)
    is_read = Column(Boolean, default=False)
    adopted = Column(Boolean, nullable=True, default=None)  # None=未操作 True=采纳 False=忽略
    adopted_at = Column(DateTime, nullable=True)
    adoption_note = Column(Text, default="")
    # V2 新增字段 — 结构化建议
    context_json = Column(Text, default="")  # 喂给AI的结构化上下文JSON
    structured_output = Column(Text, default="")  # AI返回的完整结构化JSON(V2格式)
    prompt_version = Column(String(20), default="")  # prompt版本号，用于A/B测试
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
        # 清理文本字段中的非法 JSON 字符
        def clean(v):
            if isinstance(v, str):
                return v.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
            return v

        return {
            "id": self.id,
            "advice_date": str(self.advice_date) if self.advice_date else None,
            "advice_time": str(self.advice_time) if self.advice_time else None,
            "market_summary": clean(self.market_summary),
            "portfolio_snapshot": clean(self.portfolio_snapshot),
            "advice_content": clean(self.advice_content),
            "actions": self.actions if self.actions else [],
            "opportunities": opportunities,
            "market_view": market_view,
            "overall_suggestion": clean(overall_suggestion),
            "risk_level": risk_level,
            "data_quality": self.data_quality if self.data_quality else {},
            "reasoning": clean(self.reasoning),
            "model_name": self.model_name,
            "token_usage": self.token_usage,
            "is_read": self.is_read,
            "adopted": self.adopted,
            "adopted_at": str(self.adopted_at) if self.adopted_at else None,
            "adoption_note": self.adoption_note or "",
            "context_json": clean(self.context_json),
            "structured_output": clean(self.structured_output),
            "prompt_version": self.prompt_version or "",
        }
