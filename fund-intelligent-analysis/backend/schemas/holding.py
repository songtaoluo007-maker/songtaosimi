from pydantic import BaseModel
from typing import Optional


class HoldingCreate(BaseModel):
    fund_code: str
    shares: float = 0
    cost_price: float = 0
    cost_amount: float = 0
    source: str = "manual"


class HoldingUpdate(BaseModel):
    shares: Optional[float] = None
    cost_price: Optional[float] = None
    cost_amount: Optional[float] = None


class HoldingResponse(BaseModel):
    id: int
    fund_code: str
    fund_name: str = ""
    fund_type: str = ""
    shares: float = 0
    cost_price: float = 0
    cost_amount: float = 0
    current_nav: float = 0
    current_value: float = 0
    daily_pnl: float = 0
    daily_pnl_ratio: float = 0
    daily_pnl_date: str = ""
    pnl_amount: float = 0
    pnl_ratio: float = 0
    source: str = "manual"
    is_active: bool = True

    model_config = {"from_attributes": True}


class HoldingSummary(BaseModel):
    total_value: float = 0
    total_cost: float = 0
    total_pnl: float = 0
    total_pnl_ratio: float = 0
    total_daily_pnl: float = 0
    daily_pnl_date: str = ""
    holding_count: int = 0
    allocation: list = []  # [{type, value, ratio}]
