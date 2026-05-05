from pydantic import BaseModel
from typing import Optional


class NewsResponse(BaseModel):
    id: int
    title: str
    content: str = ""
    source: str = ""
    url: str = ""
    keyword: str = ""
    sentiment: str = "neutral"
    publish_time: Optional[str] = None

    model_config = {"from_attributes": True}
