"""
基金管理 API — V2

V2 改动：
- BUG 修复：原 v1 使用 logger.debug() 但未 import logger，触发 NameError
- 移除从 technical_analysis 借 clear_proxy_env/to_float 的怪异依赖，直接用 backend.utils
- 抽出 nav_history 与 analysis 的公共采集逻辑，减少重复
- 缩小 `try/except` 范围，避免把 HTTPException 吞掉
"""
import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from loguru import logger

from backend.database import get_db
from backend.models.fund import Fund
from backend.schemas.fund import FundCreate, FundResponse
from backend.utils import clear_proxy_env, to_float

router = APIRouter(prefix="/api/funds", tags=["基金管理"])


@router.get("", response_model=List[FundResponse])
def list_funds(
    keyword: Optional[str] = None,
    fund_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Fund)
    if keyword:
        query = query.filter(
            (Fund.fund_code.contains(keyword)) | (Fund.fund_name.contains(keyword))
        )
    if fund_type:
        query = query.filter(Fund.fund_type == fund_type)
    return query.order_by(Fund.fund_code).all()


@router.get("/search/{fund_code}")
def search_fund_online(fund_code: str):
    from backend.services.fund_nav_collector import fetch_fund_info, fetch_latest_nav

    if not re.match(r"^\d{6}$", fund_code):
        raise HTTPException(status_code=400, detail="基金代码必须为6位数字")

    info = fetch_fund_info(fund_code) or {}
    if not info.get("fund_name"):
        raise HTTPException(status_code=404, detail=f"未找到基金 {fund_code}")

    info["latest_nav"] = fetch_latest_nav(fund_code)
    return info


@router.get("/{fund_code}")
def get_fund(fund_code: str, db: Session = Depends(get_db)):
    fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    return fund.to_dict()


@router.post("", response_model=FundResponse)
def create_fund(data: FundCreate, db: Session = Depends(get_db)):
    existing = db.query(Fund).filter(Fund.fund_code == data.fund_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="基金已存在")
    fund = Fund(**data.model_dump())
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


@router.delete("/{fund_code}")
def delete_fund(fund_code: str, db: Session = Depends(get_db)):
    fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    db.delete(fund)
    db.commit()
    return {"message": "删除成功"}


def _fetch_nav_dataframe(fund_code: str, limit: int):
    import akshare as ak

    df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
    if df is None or df.empty:
        return []
    df = df.tail(limit)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "date": str(row.get("净值日期", "")),
            "nav": to_float(row.get("单位净值")),
            "daily_return": to_float(row.get("日增长率")),
        })
    return rows


@router.get("/{fund_code}/nav-history")
def get_fund_nav_history(
    fund_code: str,
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    try:
        rows = _fetch_nav_dataframe(fund_code, limit)
        return {
            "fund_code": fund_code,
            "history": [{"date": r["date"], "nav": r["nav"]} for r in rows],
        }
    except Exception as e:
        logger.warning(f"基金 {fund_code} 净值历史获取失败: {e}")
        raise HTTPException(status_code=502, detail=f"获取净值历史失败: {e}")


def _stage_return(nav_rows: list[dict], days: int):
    if len(nav_rows) <= days:
        return None
    start = nav_rows[-days - 1]["nav"]
    end = nav_rows[-1]["nav"]
    return round((end - start) / start * 100, 2) if start else None


def _risk_metrics(nav_rows: list[dict]) -> dict:
    daily_returns = [r["daily_return"] for r in nav_rows if r.get("daily_return") is not None]
    if not daily_returns:
        return {"win_rate": 0, "volatility": 0, "max_drawdown": 0, "sample_days": 0}

    win_rate = sum(1 for r in daily_returns if r > 0) / len(daily_returns) * 100
    volatility = 0.0
    if len(daily_returns) > 1:
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        volatility = variance ** 0.5

    peak = None
    max_drawdown = 0.0
    for r in nav_rows:
        nav = r.get("nav") or 0
        if not nav:
            continue
        peak = nav if peak is None else max(peak, nav)
        if peak:
            drawdown = (nav - peak) / peak * 100
            max_drawdown = min(max_drawdown, drawdown)

    return {
        "win_rate": round(win_rate, 2),
        "volatility": round(volatility, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sample_days": len(daily_returns),
    }


@router.get("/{fund_code}/analysis")
def get_fund_analysis(
    fund_code: str,
    limit: int = Query(180, ge=30, le=1000),
    db: Session = Depends(get_db),
):
    clear_proxy_env()
    fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()

    try:
        nav_rows = _fetch_nav_dataframe(fund_code, limit)
    except Exception as e:
        logger.warning(f"基金 {fund_code} 净值采集失败: {e}")
        raise HTTPException(status_code=502, detail=f"获取基金分析失败: {e}")

    year = str(date.today().year)
    stock_holdings = []
    industry_allocation = []

    try:
        import akshare as ak
        hold_df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
        if hold_df is not None and not hold_df.empty:
            for _, row in hold_df.head(30).iterrows():
                stock_holdings.append({
                    "stock_code": str(row.get("股票代码", "")),
                    "stock_name": str(row.get("股票名称", "")),
                    "ratio": to_float(row.get("占净值比例")),
                    "shares": to_float(row.get("持股数")),
                    "market_value": to_float(row.get("持仓市值")),
                    "quarter": str(row.get("季度", "")),
                })
    except Exception as e:
        logger.debug(f"基金 {fund_code} 持仓明细获取失败: {e}")

    try:
        import akshare as ak
        ind_df = ak.fund_portfolio_industry_allocation_em(symbol=fund_code, date=year)
        if ind_df is not None and not ind_df.empty:
            for _, row in ind_df.head(20).iterrows():
                industry_allocation.append({
                    "industry": str(row.get("行业类别") or row.get("行业名称") or ""),
                    "ratio": to_float(row.get("占净值比例")),
                    "market_value": to_float(row.get("市值")),
                })
    except Exception as e:
        logger.debug(f"基金 {fund_code} 行业配置获取失败: {e}")

    holding = None
    try:
        from backend.models.holding import Holding

        holding_model = db.query(Holding).filter(
            Holding.fund_code == fund_code,
            Holding.is_active == True,
        ).first()
        if holding_model:
            holding = holding_model.to_dict()
    except Exception as e:
        logger.debug(f"基金 {fund_code} 持仓查询失败: {e}")

    latest_daily_return = nav_rows[-1].get("daily_return") if nav_rows else None
    if holding and holding.get("daily_pnl_ratio"):
        latest_daily_return = holding.get("daily_pnl_ratio")

    return {
        "fund_code": fund_code,
        "fund_name": fund.fund_name if fund else "",
        "fund_type": fund.fund_type if fund else "",
        "holding": holding,
        "latest_daily_return": latest_daily_return,
        "nav_history": nav_rows,
        "returns": {
            "1w": _stage_return(nav_rows, 5),
            "1m": _stage_return(nav_rows, 20),
            "3m": _stage_return(nav_rows, 60),
            "6m": _stage_return(nav_rows, 120),
            "1y": _stage_return(nav_rows, 240),
        },
        "risk_metrics": _risk_metrics(nav_rows),
        "stock_holdings": stock_holdings,
        "industry_allocation": industry_allocation,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
