"""
用户决策复盘 API — P2.2
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.decision_review_service_v3 import (
    compute_behavior_bias, list_decisions, list_recent_snapshots,
    persist_monthly_snapshot, run_full_review,
)

router = APIRouter(prefix="/api/decision-review", tags=["用户决策复盘"])


@router.get("/bias")
def get_bias(month: str | None = Query(None), db: Session = Depends(get_db)):
    """获取行为偏差雷达图数据（默认本月，不持久化）"""
    return compute_behavior_bias(db, month=month)


@router.post("/bias/persist")
def post_persist(month: str | None = Query(None), db: Session = Depends(get_db)):
    """计算并持久化某月雷达图"""
    return persist_monthly_snapshot(db, month=month)


@router.get("/bias/history")
def get_history(limit: int = Query(12, ge=1, le=60), db: Session = Depends(get_db)):
    return {"items": list_recent_snapshots(db, limit=limit)}


@router.get("/decisions")
def get_decisions(month: str | None = Query(None),
                  limit: int = Query(100, ge=1, le=500),
                  db: Session = Depends(get_db)):
    return {"items": list_decisions(db, month=month, limit=limit)}


@router.post("/run")
def post_run(db: Session = Depends(get_db)):
    """完整跑一遍：生成快照 + 回填 30d 结果 + 当月雷达图"""
    return run_full_review(db)
