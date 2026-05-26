from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from backend.database import get_db
from backend.models.trade import Trade
from backend.schemas.trade import TradeCreate, TradeResponse

router = APIRouter(prefix="/api/trades", tags=["交易记录"])


@router.get("")
def list_trades(
    fund_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    trade_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """交易记录列表"""
    query = db.query(Trade)
    if fund_code:
        query = query.filter(Trade.fund_code == fund_code)
    if start_date:
        query = query.filter(Trade.trade_date >= start_date)
    if end_date:
        query = query.filter(Trade.trade_date <= end_date)
    if trade_type:
        query = query.filter(Trade.trade_type == trade_type)
    trades = query.order_by(Trade.trade_date.desc()).all()
    return [t.to_dict() for t in trades]


@router.post("")
def create_trade(data: TradeCreate, db: Session = Depends(get_db)):
    """新增交易记录"""
    from backend.models.fund import Fund
    fund = db.query(Fund).filter(Fund.fund_code == data.fund_code).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")

    trade = Trade(**data.model_dump())
    db.add(trade)

    # 自动更新持仓
    from backend.models.holding import Holding
    holding = db.query(Holding).filter(
        Holding.fund_code == data.fund_code,
        Holding.is_active == True,
    ).first()

    if data.trade_type == "买入":
        if holding:
            # 加仓：加权平均成本
            old_total = float(holding.cost_amount or 0)
            new_total = old_total + data.amount
            old_shares = float(holding.shares or 0)
            new_shares = old_shares + data.shares
            holding.shares = new_shares
            holding.cost_amount = new_total
            holding.cost_price = new_total / new_shares if new_shares > 0 else 0
        else:
            # 新建仓
            holding = Holding(
                fund_code=data.fund_code,
                shares=data.shares,
                cost_price=data.nav_price,
                cost_amount=data.amount,
                current_nav=float(fund.latest_nav or 0),
                current_value=data.shares * float(fund.latest_nav or 0),
                source=data.source,
                is_active=True,
            )
            db.add(holding)
    elif data.trade_type == "卖出":
        if holding:
            current_shares = float(holding.shares or 0)
            if current_shares <= 0:
                holding.is_active = False
                holding.shares = 0
            else:
                remaining_shares = current_shares - data.shares
                if remaining_shares <= 0:
                    holding.is_active = False
                    holding.shares = 0
                else:
                    ratio = data.shares / current_shares
                    holding.shares = remaining_shares
                    holding.cost_amount = float(holding.cost_amount or 0) * (1 - ratio)

    db.commit()
    db.refresh(trade)
    return trade.to_dict()


@router.put("/{trade_id}")
def update_trade(trade_id: int, data: TradeCreate, db: Session = Depends(get_db)):
    """编辑交易记录。只更新记录本身，持仓可通过持仓刷新/手动调整校准。"""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    for key, value in data.model_dump().items():
        setattr(trade, key, value)
    db.commit()
    db.refresh(trade)
    return trade.to_dict()


@router.delete("/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    """删除交易记录。"""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    db.delete(trade)
    db.commit()
    return {"message": "交易记录已删除"}


@router.get("/stats")
def trade_stats(db: Session = Depends(get_db)):
    """交易统计"""
    from sqlalchemy import func
    buy_total = db.query(func.sum(Trade.amount)).filter(Trade.trade_type == "买入").scalar() or 0
    sell_total = db.query(func.sum(Trade.amount)).filter(Trade.trade_type == "卖出").scalar() or 0
    fee_total = db.query(func.sum(Trade.fee)).scalar() or 0
    count = db.query(Trade).count()
    return {
        "buy_total": float(buy_total),
        "sell_total": float(sell_total),
        "fee_total": float(fee_total),
        "trade_count": count,
    }
