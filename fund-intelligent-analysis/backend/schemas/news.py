from pydantic import BaseModel, Field
from typing import Optional, Any


class NewsResponse(BaseModel):
    id: int
    title: str
    content: str = ""
    source: str = ""
    url: str = ""
    keyword: str = ""
    sentiment: str = "neutral"
    category: str = "推荐"
    sub_category: str = "全部"
    importance_score: float = 50
    impact_items: list[dict[str, Any]] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)
    is_breaking: bool = False
    publish_time: Optional[str] = None

    model_config = {"from_attributes": True}
