"""
费率账本 API — P2.1
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.fund_fee_service_v3 import (
    daily_fee_accrual, estimate_redemption_fee, get_fee_schedule,
    list_fee_schedules, upsert_fee_schedule, yearly_ledger,
)

router = APIRouter(prefix="/api/fund-fees", tags=["费率账本"])


@router.get("/schedules")
def get_schedules(db: Session = Depends(get_db)):
    return {"items": list_fee_schedules(db)}


@router.get("/schedules/{fund_code}")
def get_one(fund_code: str, db: Session = Depends(get_db)):
    item = get_fee_schedule(db, fund_code)
    if not item:
        raise HTTPException(status_code=404, detail="未配置该基金的费率")
    return item


@router.put("/schedules/{fund_code}")
def put_schedule(fund_code: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    return upsert_fee_schedule(db, fund_code, payload)


@router.post("/accrual/run")
def run_accrual(db: Session = Depends(get_db)):
    """手动触发"今日费率计提"（与每日 21:00 定时任务同源）"""
    return daily_fee_accrual(db)


@router.get("/ledger/yearly")
def yearly(year: int | None = Query(None), db: Session = Depends(get_db)):
    return yearly_ledger(db, year=year)


@router.get("/redemption-estimate/{fund_code}")
def redemption(
    fund_code: str,
    redeem_shares: float | None = Query(None),
    redeem_amount: float | None = Query(None),
    db: Session = Depends(get_db),
):
    """赎回前必看：根据持有天数 + 费率档计算扣费 + 节省提示"""
    result = estimate_redemption_fee(db, fund_code, redeem_shares=redeem_shares, redeem_amount=redeem_amount)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
