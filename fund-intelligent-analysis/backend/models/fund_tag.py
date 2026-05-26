from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, func
from backend.database import Base


class FundTag(Base):
    """基金标签 — 行业/主题/风格/风险等级"""
    __tablename__ = "fund_tags"
    __table_args__ = (
        Index("ix_fund_tag_code_type", "fund_code", "tag_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), ForeignKey("funds.fund_code"), nullable=False)
    tag_type = Column(String(20), nullable=False, comment="industry/theme/style/risk")
    tag_name = Column(String(50), nullable=False, comment="标签名，如 半导体/AI算力/成长/高")
    tag_value = Column(Float, default=1.0, comment="暴露权重 0-1，用于聚合计算")
    source = Column(String(10), default="ai", comment="ai/manual")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "fund_code": self.fund_code,
            "tag_type": self.tag_type,
            "tag_name": self.tag_name,
            "tag_value": round(self.tag_value, 4) if self.tag_value else 1.0,
            "source": self.source,
        }
