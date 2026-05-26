"""
基金经理 + 预警 API — P0.2
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.fund_manager_service_v3 import (
    get_fund_managers,
    list_alerts,
    mark_alert_read,
    sync_all_holding_managers,
    sync_fund_managers,
)

router = APIRouter(tags=["基金经理"])


@router.get("/api/funds/{fund_code}/managers")
def fund_managers(fund_code: str, db: Session = Depends(get_db)):
    """获取某只基金的历任 + 现任经理"""
    return get_fund_managers(db, fund_code)


@router.post("/api/funds/{fund_code}/managers/sync")
def sync_single(fund_code: str, db: Session = Depends(get_db)):
    """立即同步单只基金的经理信息（拉东方财富 + 写预警）"""
    return sync_fund_managers(db, fund_code)


@router.post("/api/manager-alerts/sync-all")
def sync_all(db: Session = Depends(get_db)):
    """全量同步所有活跃持仓基金的经理变化（与定时任务同源）"""
    return sync_all_holding_managers(db)


@router.get("/api/manager-alerts")
def manager_alerts(
    only_unread: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """经理变更预警列表（默认仅未读，severity 由高到低排）"""
    return {"items": list_alerts(db, only_unread=only_unread, limit=limit)}


@router.put("/api/manager-alerts/{alert_id}/read")
def alert_mark_read(alert_id: int, db: Session = Depends(get_db)):
    if not mark_alert_read(db, alert_id):
        raise HTTPException(status_code=404, detail="预警不存在")
    return {"message": "已标记已读", "alert_id": alert_id}
