"""
AI 建议复盘 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.advice_review_service import (
    generate_review,
    batch_review_pending,
    get_hit_rate_stats,
    get_review_list,
)

router = APIRouter(prefix="/api/ai/review", tags=["AI复盘"])


@router.get("/stats")
def review_stats(days: int = Query(90, ge=7, le=365), db: Session = Depends(get_db)):
    """命中率统计"""
    return get_hit_rate_stats(db, days)


@router.get("/list")
def review_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    """复盘列表"""
    return get_review_list(db, page, page_size)


@router.post("/{advice_id}")
def review_single(advice_id: int, db: Session = Depends(get_db)):
    """复盘单条建议"""
    result = generate_review(db, advice_id)
    if not result:
        raise HTTPException(status_code=404, detail="建议不存在或数据不足")
    return result.to_dict()


@router.post("/batch")
def review_batch(db: Session = Depends(get_db)):
    """批量复盘所有未复盘的够天数建议"""
    result = batch_review_pending(db)
    return result
