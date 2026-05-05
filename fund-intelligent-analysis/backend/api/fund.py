import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models.fund import Fund
from backend.schemas.fund import FundCreate, FundUpdate, FundResponse

router = APIRouter(prefix="/api/funds", tags=["基金管理"])


@router.get("", response_model=List[FundResponse])
def list_funds(
    keyword: Optional[str] = None,
    fund_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """基金列表，支持关键词搜索和类型筛选"""
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
    """联网搜索基金信息"""
    from backend.services.fund_nav_collector import fetch_fund_info, fetch_latest_nav

    if not re.match(r'^\d{6}$', fund_code):
        raise HTTPException(status_code=400, detail="基金代码必须为6位数字")

    info = fetch_fund_info(fund_code)
    if not info.get("fund_name"):
        raise HTTPException(status_code=404, detail=f"未找到基金 {fund_code}")

    # 同时获取最新净值
    nav = fetch_latest_nav(fund_code)
    info["latest_nav"] = nav

    return info


@router.get("/{fund_code}")
def get_fund(fund_code: str, db: Session = Depends(get_db)):
    """获取基金详情"""
    fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    return fund.to_dict()


@router.post("", response_model=FundResponse)
def create_fund(data: FundCreate, db: Session = Depends(get_db)):
    """手动添加基金"""
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
    """删除基金"""
    fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    db.delete(fund)
    db.commit()
    return {"message": "删除成功"}


@router.get("/{fund_code}/nav-history")
def get_fund_nav_history(fund_code: str, limit: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """获取基金净值历史（从AKShare在线获取）"""
    try:
        import akshare as ak
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is not None and not df.empty:
            df = df.tail(limit)
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row.get("净值日期", "")),
                    "nav": float(row.get("单位净值", 0)),
                })
            return {"fund_code": fund_code, "history": records}
        return {"fund_code": fund_code, "history": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取净值历史失败: {str(e)}")


@router.get("/{fund_code}/analysis")
def get_fund_analysis(fund_code: str, limit: int = Query(180, ge=30, le=1000), db: Session = Depends(get_db)):
    """基金详情分析：净值走势、阶段收益、持仓股票、行业配置。"""
    from datetime import date
    from backend.services.technical_analysis import clear_proxy_env, to_float

    clear_proxy_env()
    fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
    try:
        import akshare as ak
        nav_df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        nav_rows = []
        if nav_df is not None and not nav_df.empty:
            nav_df = nav_df.tail(limit)
            for _, row in nav_df.iterrows():
                nav_rows.append({
                    "date": str(row.get("净值日期", "")),
                    "nav": to_float(row.get("单位净值")),
                    "daily_return": to_float(row.get("日增长率")),
                })

        def stage_return(days: int):
            if len(nav_rows) <= days:
                return None
            start = nav_rows[-days - 1]["nav"]
            end = nav_rows[-1]["nav"]
            return round((end - start) / start * 100, 2) if start else None

        year = str(date.today().year)
        holdings = []
        try:
            hold_df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
            if hold_df is not None and not hold_df.empty:
                for _, row in hold_df.head(30).iterrows():
                    holdings.append({
                        "stock_code": str(row.get("股票代码", "")),
                        "stock_name": str(row.get("股票名称", "")),
                        "ratio": to_float(row.get("占净值比例")),
                        "shares": to_float(row.get("持股数")),
                        "market_value": to_float(row.get("持仓市值")),
                        "quarter": str(row.get("季度", "")),
                    })
        except Exception:
            pass

        industries = []
        try:
            ind_df = ak.fund_portfolio_industry_allocation_em(symbol=fund_code, date=year)
            if ind_df is not None and not ind_df.empty:
                for _, row in ind_df.head(20).iterrows():
                    industries.append({
                        "industry": str(row.get("行业类别") or row.get("行业名称") or ""),
                        "ratio": to_float(row.get("占净值比例")),
                        "market_value": to_float(row.get("市值")),
                    })
        except Exception:
            pass

        return {
            "fund_code": fund_code,
            "fund_name": fund.fund_name if fund else "",
            "fund_type": fund.fund_type if fund else "",
            "nav_history": nav_rows,
            "returns": {
                "1w": stage_return(5),
                "1m": stage_return(20),
                "3m": stage_return(60),
                "6m": stage_return(120),
                "1y": stage_return(240),
            },
            "stock_holdings": holdings,
            "industry_allocation": industries,
            "updated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取基金分析失败: {str(e)}")
