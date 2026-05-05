from pydantic import BaseModel
from typing import Optional


class MarketSnapshotResponse(BaseModel):
    id: int
    symbol: str
    name: str
    snapshot_type: str
    price: float = 0
    change_pct: float = 0
    change_amount: float = 0
    volume: int = 0
    high: float = 0
    low: float = 0
    open: float = 0
    prev_close: float = 0
    snapshot_date: Optional[str] = None
    snapshot_time: Optional[str] = None

    model_config = {"from_attributes": True}
