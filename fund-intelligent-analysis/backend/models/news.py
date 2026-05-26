import json

from sqlalchemy import Column, Integer, String, Text, DateTime, Index, Numeric, Boolean, func
from backend.database import Base


class News(Base):
    __tablename__ = "news"
    __table_args__ = (
        Index("ix_news_keyword_time", "keyword", "publish_time"),
        Index("idx_news_publish", "publish_time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    source = Column(String(50), default="")  # 东方财富/新浪财经
    url = Column(String(500), default="")
    keyword = Column(String(50), default="")  # 关联关键词
    sentiment = Column(String(10), default="neutral")  # positive/neutral/negative
    category = Column(String(20), default="推荐")
    sub_category = Column(String(20), default="全部")
    importance_score = Column(Numeric(6, 2), default=50)
    impact_items = Column(Text, default="[]")
    related_topics = Column(Text, default="[]")
    is_breaking = Column(Boolean, default=False)
    publish_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        impact_items = _loads_json(self.impact_items, [])
        related_topics = _loads_json(self.related_topics, [])
        if not impact_items and self.title:
            try:
                from backend.services.news_classifier import classify_news

                classified = classify_news(self.title, self.content, self.source, self.keyword)
                impact_items = classified.get("impact_items", [])
                related_topics = classified.get("related_topics", [])
            except Exception:
                pass
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "url": self.url,
            "keyword": self.keyword,
            "sentiment": self.sentiment,
            "category": self.category or "推荐",
            "sub_category": self.sub_category or "全部",
            "importance_score": float(self.importance_score) if self.importance_score is not None else 50,
            "impact_items": impact_items,
            "related_topics": related_topics,
            "is_breaking": bool(self.is_breaking),
            "publish_time": str(self.publish_time) if self.publish_time else None,
        }


def _loads_json(value, default):
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default
