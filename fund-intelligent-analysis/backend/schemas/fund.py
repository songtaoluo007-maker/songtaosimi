from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import date


class FundCreate(BaseModel):
    fund_code: str
    fund_name: str
    fund_type: str = "混合型"
    benchmark: str = ""
    risk_level: str = ""
    manager: str = ""
    company: str = ""


class FundUpdate(BaseModel):
    fund_name: Optional[str] = None
    fund_type: Optional[str] = None
    benchmark: Optional[str] = None
    risk_level: Optional[str] = None
    manager: Optional[str] = None
    company: Optional[str] = None


class FundResponse(BaseModel):
    id: int
    fund_code: str
    fund_name: str
    fund_type: str
    latest_nav: float = 0
    latest_nav_date: Optional[date] = None
    acc_nav: float = 0

    model_config = {"from_attributes": True}

    @field_serializer("latest_nav_date")
    def serialize_date(self, value: date | None) -> str | None:
        return value.isoformat() if value else None
