from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.return_metrics_v3 import (
    get_benchmark_compare_report,
    get_drawdown_report,
    get_xirr_report,
    save_daily_snapshot,
)

router = APIRouter(prefix="/api/holdings/metrics", tags=["持仓专业指标"])


@router.get("/xirr")
def holdings_xirr(db: Session = Depends(get_db)):
    """组合与单基金 XIRR 年化收益率。"""
    return get_xirr_report(db)


@router.get("/drawdown")
def holdings_drawdown(db: Session = Depends(get_db)):
    """组合与单基金最大回撤、当前回撤和恢复天数。"""
    return get_drawdown_report(db)


@router.get("/benchmark-compare")
def holdings_benchmark_compare(db: Session = Depends(get_db)):
    """持仓基金相对基准表现，默认基准为沪深300。"""
    return get_benchmark_compare_report(db)


@router.post("/snapshot")
def snapshot_portfolio(db: Session = Depends(get_db)):
    """立即保存今日组合市值快照。"""
    return save_daily_snapshot(db=db)
