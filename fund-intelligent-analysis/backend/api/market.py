from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.database import get_db
from backend.models.market_snapshot import MarketSnapshot

router = APIRouter(prefix="/api/market", tags=["行情数据"])


@router.get("/indices")
def get_a_share_indices(db: Session = Depends(get_db)):
    """当前A股主要指数行情"""
    from datetime import date
    today = date.today()
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == "index",
        MarketSnapshot.snapshot_date == today,
    ).order_by(MarketSnapshot.snapshot_time.desc()).all()
    if not snapshots:
        try:
            from backend.services.market_collector import collect_a_share_indices
            collect_a_share_indices()
            db.expire_all()
            snapshots = db.query(MarketSnapshot).filter(
                MarketSnapshot.snapshot_type == "index",
                MarketSnapshot.snapshot_date == today,
            ).order_by(MarketSnapshot.snapshot_time.desc()).all()
        except Exception:
            snapshots = []

    # 去重：每个symbol取最新
    seen = set()
    result = []
    for s in snapshots:
        if s.symbol not in seen:
            seen.add(s.symbol)
            result.append(s.to_dict())
    return result


@router.post("/refresh")
def refresh_market_data():
    """手动刷新指数、行业和概念板块行情"""
    from backend.services.market_collector import collect_a_share_indices, collect_concepts, collect_sectors

    collect_a_share_indices()
    collect_sectors()
    collect_concepts()
    return {"message": "行情数据已刷新"}


@router.get("/board-rankings")
def get_live_board_rankings(
    snapshot_type: str = Query("sector", enum=["sector", "concept"]),
    limit: int = Query(20, ge=5, le=50),
):
    """行业/概念交易日热度与资金流入排行"""
    try:
        from backend.services.market_collector import get_board_rankings
        return get_board_rankings(snapshot_type, limit)
    except Exception as e:
        return {
            "snapshot_type": snapshot_type,
            "heat_top": [],
            "inflow_top": [],
            "updated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "unavailable",
            "warning": str(e),
        }


@router.get("/sectors")
def get_sectors(
    snapshot_type: str = Query("sector", enum=["sector", "concept"]),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """行业/概念板块涨跌排行"""
    from datetime import date
    today = date.today()
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == snapshot_type,
        MarketSnapshot.snapshot_date == today,
    ).order_by(MarketSnapshot.change_pct.desc()).all()

    if not snapshots:
        latest = db.query(MarketSnapshot.snapshot_date).filter(
            MarketSnapshot.snapshot_type == snapshot_type,
        ).order_by(MarketSnapshot.snapshot_date.desc()).first()
        if latest:
            snapshots = db.query(MarketSnapshot).filter(
                MarketSnapshot.snapshot_type == snapshot_type,
                MarketSnapshot.snapshot_date == latest[0],
            ).order_by(MarketSnapshot.change_pct.desc()).all()

    if not snapshots:
        try:
            if snapshot_type == "concept":
                from backend.services.market_collector import collect_concepts
                collect_concepts()
            else:
                from backend.services.market_collector import collect_sectors
                collect_sectors()
            db.expire_all()
            snapshots = db.query(MarketSnapshot).filter(
                MarketSnapshot.snapshot_type == snapshot_type,
                MarketSnapshot.snapshot_date == today,
            ).order_by(MarketSnapshot.change_pct.desc()).all()
        except Exception:
            snapshots = []

    seen = set()
    result = []
    for s in snapshots:
        if s.symbol not in seen:
            seen.add(s.symbol)
            result.append(s.to_dict())
    return result[:limit]


@router.get("/global")
def get_global_indices(db: Session = Depends(get_db)):
    """全球主要指数"""
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.snapshot_type == "global",
    ).order_by(MarketSnapshot.snapshot_date.desc(), MarketSnapshot.snapshot_time.desc()).all()

    seen = set()
    result = []
    for s in snapshots:
        if s.symbol not in seen:
            seen.add(s.symbol)
            result.append(s.to_dict())
    return result


@router.get("/fund-estimate/{fund_code}")
def get_fund_estimate(fund_code: str):
    """单只基金实时估值（从东方财富在线获取）"""
    try:
        import httpx
        import json
        import time

        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        resp = httpx.get(url, params={"rt": int(time.time() * 1000)}, timeout=10)
        text = resp.text
        # JSONP格式: jsonpgz({...})
        json_str = text[text.index("(") + 1 : text.rindex(")")]
        data = json.loads(json_str)
        return {
            "fund_code": data.get("fundcode", fund_code),
            "fund_name": data.get("name", ""),
            "estimated_nav": float(data.get("gsz", 0)),
            "estimated_change_pct": float(data.get("gszzl", 0)),
            "estimate_time": data.get("gztime", ""),
            "last_nav": float(data.get("dwjz", 0)),
        }
    except Exception as e:
        return {"error": f"获取基金估值失败: {str(e)}", "fund_code": fund_code}


@router.get("/history/{symbol}")
def get_market_history(
    symbol: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """行情历史数据"""
    from datetime import date, timedelta
    start_date = date.today() - timedelta(days=days)
    snapshots = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == symbol,
        MarketSnapshot.snapshot_date >= start_date,
    ).order_by(MarketSnapshot.snapshot_date).all()
    return [s.to_dict() for s in snapshots]


@router.get("/detail/{symbol}")
def get_market_detail(
    symbol: str,
    name: Optional[str] = None,
    snapshot_type: str = Query("index", enum=["index", "sector", "concept", "global"]),
    period: str = Query("daily", enum=["intraday", "daily", "weekly", "monthly"]),
    limit: int = Query(120, ge=20, le=500),
    db: Session = Depends(get_db),
):
    """指数/板块详情：分时、K线和技术指标"""
    from backend.services.technical_analysis import (
        fetch_board_history,
        fetch_board_intraday,
        fetch_global_history,
        fetch_global_intraday,
        fetch_index_history,
        fetch_index_intraday,
    )

    display_name = name
    if not display_name:
        latest = db.query(MarketSnapshot).filter(MarketSnapshot.symbol == symbol).order_by(
            MarketSnapshot.snapshot_date.desc(),
            MarketSnapshot.snapshot_time.desc(),
        ).first()
        display_name = latest.name if latest else symbol

    try:
        if period == "intraday":
            if snapshot_type == "index":
                rows = fetch_index_intraday(symbol)
            elif snapshot_type == "global":
                rows = fetch_global_intraday(symbol, display_name)
            else:
                rows = fetch_board_intraday(display_name, snapshot_type)
        else:
            if snapshot_type == "index":
                rows = fetch_index_history(symbol, period, limit)
            elif snapshot_type == "global":
                rows = fetch_global_history(symbol, display_name, period, limit)
            else:
                rows = fetch_board_history(display_name, snapshot_type, period, limit)
        return {
            "symbol": symbol,
            "name": display_name,
            "snapshot_type": snapshot_type,
            "period": period,
            "rows": rows,
            "latest": rows[-1] if rows else None,
            "updated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "online",
        }
    except Exception as e:
        # 线上接口不稳定时回退本地快照，保证页面可用
        snapshots = db.query(MarketSnapshot).filter(MarketSnapshot.symbol == symbol).order_by(
            MarketSnapshot.snapshot_date.desc(),
            MarketSnapshot.snapshot_time.desc(),
        ).limit(limit).all()
        rows = []
        for s in reversed(snapshots):
            rows.append({
                "date": str(s.snapshot_date),
                "open": float(s.open or s.price or 0),
                "close": float(s.price or 0),
                "high": float(s.high or s.price or 0),
                "low": float(s.low or s.price or 0),
                "volume": int(s.volume or 0),
                "turnover": float(s.turnover or 0),
                "change_pct": float(s.change_pct or 0),
            })
        return {
            "symbol": symbol,
            "name": display_name,
            "snapshot_type": snapshot_type,
            "period": period,
            "rows": rows,
            "latest": rows[-1] if rows else None,
            "updated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "local_snapshot",
            "warning": str(e),
        }
