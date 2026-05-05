from pydantic import BaseModel
from typing import Optional
from datetime import date


class TradeCreate(BaseModel):
    fund_code: str
    trade_type: str  # 买入/卖出
    shares: float = 0
    nav_price: float = 0
    amount: float = 0
    fee: float = 0
    trade_date: date
    confirm_date: Optional[date] = None
    source: str = "manual"
    note: str = ""


class TradeResponse(BaseModel):
    id: int
    fund_code: str
    fund_name: str = ""
    trade_type: str
    shares: float = 0
    nav_price: float = 0
    amount: float = 0
    fee: float = 0
    trade_date: Optional[str] = None
    confirm_date: Optional[str] = None
    source: str = "manual"
    note: str = ""

    model_config = {"from_attributes": True}
