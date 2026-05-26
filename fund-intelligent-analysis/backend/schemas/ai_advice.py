from pydantic import BaseModel, Field
from typing import Optional, List, Any


class AiAdviceResponse(BaseModel):
    id: int
    advice_date: Optional[str] = None
    advice_time: Optional[str] = None
    advice_content: str = ""
    actions: List[Any] = Field(default_factory=list)
    market_view: str = "neutral"
    overall_suggestion: str = ""
    risk_level: str = "medium"
    data_quality: dict = Field(default_factory=dict)
    reasoning: str = ""
    model_name: str = ""
    token_usage: int = 0
    is_read: bool = False

    model_config = {"from_attributes": True, "protected_namespaces": ()}
