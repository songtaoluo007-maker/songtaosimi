"""
定投计划 API — P1.1
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.investment_plan_service_v3 import (
    create_plan, deactivate_plan, list_plans,
    daily_check_and_alert, reconcile_with_trades, smile_curve_data,
    update_plan, upcoming_executions,
)
from backend.models.investment_plan import InvestmentPlan

router = APIRouter(prefix="/api/investment-plans", tags=["定投计划"])


@router.get("")
def list_(active_only: bool = Query(True), db: Session = Depends(get_db)):
    """计划列表 + 每个计划的进度统计"""
    return {"items": list_plans(db, active_only=active_only)}


@router.post("")
def create(payload: dict = Body(...), db: Session = Depends(get_db)):
    required = ("fund_code", "plan_type", "amount", "start_date")
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"缺少必填字段: {','.join(missing)}")
    if payload["plan_type"] not in {"daily", "weekly", "biweekly", "monthly"}:
        raise HTTPException(status_code=400, detail="plan_type 必须为 daily/weekly/biweekly/monthly")
    plan = create_plan(db, payload)
    return plan.to_dict()


@router.put("/{plan_id}")
def update(plan_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    plan = update_plan(db, plan_id, payload)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan.to_dict()


@router.delete("/{plan_id}")
def deactivate(plan_id: int, db: Session = Depends(get_db)):
    if not deactivate_plan(db, plan_id):
        raise HTTPException(status_code=404, detail="计划不存在")
    return {"message": "已停用"}


@router.get("/upcoming")
def upcoming(days_ahead: int = Query(7, ge=1, le=60), db: Session = Depends(get_db)):
    """未来 N 天应执行的定投期"""
    return {"items": upcoming_executions(db, days_ahead=days_ahead)}


@router.get("/{plan_id}/smile-curve")
def smile(plan_id: int, db: Session = Depends(get_db)):
    """定投微笑曲线（NAV + 每期定投点 + 摊薄成本线）"""
    data = smile_curve_data(db, plan_id)
    if data.get("error"):
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.post("/{plan_id}/reconcile")
def reconcile(plan_id: int, db: Session = Depends(get_db)):
    """把 trades 表中同日同代码的买入交易关联到本计划的执行记录"""
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    matched = reconcile_with_trades(db, plan)
    return {"matched": matched}


@router.post("/check-due")
def check_due(db: Session = Depends(get_db)):
    """手动触发"今日到期检查"（与每日 9:00 定时任务同源）"""
    return daily_check_and_alert(db)
