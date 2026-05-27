"""
老基民工具集 API — P2.4
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.senior_toolbox_service_v3 import (
    daily_milestone_check, fee_health_summary, holding_milestones,
    holiday_alerts, quarterly_disclosure, switch_savings,
)

router = APIRouter(prefix="/api/toolbox", tags=["工具集"])


@router.get("/milestones")
def get_milestones(db: Session = Depends(get_db)):
    """持有时长里程碑 + 距离下个降费档天数"""
    return holding_milestones(db)


@router.get("/quarterly-disclosure")
def get_quarterly(db: Session = Depends(get_db)):
    """季报披露日历 + 持仓基金披露状态"""
    return quarterly_disclosure(db)


@router.get("/switch-savings")
def get_switch_savings(
    from_code: str = Query(...),
    to_code: str = Query(...),
    amount: float | None = Query(None),
    convert_fee_rate: float = Query(0.005, ge=0, le=0.05),
    db: Session = Depends(get_db),
):
    """同公司基金转换 vs 赎回再申购费率对比"""
    return switch_savings(db, from_code, to_code,
                          amount=amount, convert_fee_rate=convert_fee_rate)


@router.get("/holidays")
def get_holidays():
    """未来 30 天节假日提醒 + 长假前后建议"""
    return holiday_alerts()


@router.get("/fee-health")
def get_fee_health(db: Session = Depends(get_db)):
    """全持仓费率体检"""
    return fee_health_summary(db)


@router.post("/milestones/run-check")
def post_milestone_check(db: Session = Depends(get_db)):
    """手动触发里程碑检查（与每日 9:30 调度同源）"""
    return daily_milestone_check(db)
