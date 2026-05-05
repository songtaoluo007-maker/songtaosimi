from sqlalchemy import Column, Integer, String, Text, DateTime, Index, func
from backend.database import Base


class News(Base):
    __tablename__ = "news"
    __table_args__ = (
        Index("ix_news_keyword_time", "keyword", "publish_time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    source = Column(String(50), default="")  # 东方财富/新浪财经
    url = Column(String(500), default="")
    keyword = Column(String(50), default="")  # 关联关键词
    sentiment = Column(String(10), default="neutral")  # positive/neutral/negative
    publish_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "url": self.url,
            "keyword": self.keyword,
            "sentiment": self.sentiment,
            "publish_time": str(self.publish_time) if self.publish_time else None,
        }
