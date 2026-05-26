"""
目标资产配置 + 再平衡 API — P1.2
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.asset_allocation_service_v3 import (
    acknowledge_alert, compute_current_allocation, compute_deviations,
    list_alerts, list_targets, reset_targets, upsert_targets,
)

router = APIRouter(prefix="/api/asset-allocation", tags=["资产配置"])


@router.get("/targets")
def get_targets(db: Session = Depends(get_db)):
    return {"items": list_targets(db)}


@router.put("/targets")
def put_targets(items: list[dict] = Body(...), db: Session = Depends(get_db)):
    """批量 upsert 目标，前端整组保存"""
    # 校验总和
    total = sum(float(it.get("target_pct") or 0) for it in items)
    if abs(total - 100) > 1.0:
        raise HTTPException(
            status_code=400,
            detail=f"目标占比合计 {total:.1f}%，应接近 100%",
        )
    saved = upsert_targets(db, items)
    return {"saved": saved, "total": total}


@router.delete("/targets")
def reset_all(db: Session = Depends(get_db)):
    n = reset_targets(db)
    return {"deleted": n}


@router.get("/current")
def get_current(db: Session = Depends(get_db)):
    """当前各大类实际占比"""
    return compute_current_allocation(db)


@router.get("/deviations")
def get_deviations(persist: bool = Query(False), db: Session = Depends(get_db)):
    """对比当前 vs 目标；persist=true 会写入 rebalance_alerts 表"""
    return compute_deviations(db, persist=persist)


@router.get("/alerts")
def alerts(only_unack: bool = Query(True), db: Session = Depends(get_db)):
    return {"items": list_alerts(db, only_unack=only_unack)}


@router.put("/alerts/{alert_id}/ack")
def ack(alert_id: int, db: Session = Depends(get_db)):
    if not acknowledge_alert(db, alert_id):
        raise HTTPException(status_code=404, detail="预警不存在")
    return {"message": "已确认"}
