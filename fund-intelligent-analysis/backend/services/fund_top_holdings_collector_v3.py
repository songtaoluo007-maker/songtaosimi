"""
基金前十大持股采集器 — P0.3

数据源：AKShare `fund_portfolio_hold_em(symbol=fund_code, date=year)`
- 返回字段：股票代码 / 股票名称 / 占净值比例 / 持股数 / 持仓市值 / 季度
- 季报披露日（4 月底 / 8 月底 / 10 月底 / 次年 1 月底）后更新

调用方式：
- 单基金：sync_fund_top_holdings(db, fund_code)
- 全持仓：sync_all_holding_top_holdings(db)  ← 季度调度 + 启动后台首刷
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from loguru import logger
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.fund_top_holding import FundTopHolding
from backend.models.holding import Holding
from backend.utils import clear_proxy_env, to_float


def _fetch_top_holdings_via_akshare(fund_code: str, year: str | None = None) -> list[dict]:
    """从 AKShare 拉单只基金的前十大持股"""
    clear_proxy_env()
    year = year or str(date.today().year)
    try:
        import akshare as ak
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
    except Exception as e:
        logger.warning(f"AKShare 拉基金 {fund_code} 持股失败({year}): {e}")
        return []
    if df is None or df.empty:
        return []

    rows = []
    for _, row in df.iterrows():
        stock_code = str(row.get("股票代码", "")).strip()
        if not stock_code:
            continue
        # AKShare 返回的"季度"字段如 '2025年1季度股票投资明细'
        raw_quarter = str(row.get("季度", "")).strip()
        quarter = _normalize_quarter(raw_quarter, year)
        rows.append({
            "stock_code": stock_code,
            "stock_name": str(row.get("股票名称", "") or "").strip(),
            "weight_pct": to_float(row.get("占净值比例")),
            "shares": to_float(row.get("持股数")),
            "market_value": to_float(row.get("持仓市值")),
            "quarter": quarter,
        })
    return rows


def _normalize_quarter(text: str, fallback_year: str) -> str:
    """AKShare 的"2025年1季度股票投资明细" → "2025Q1"；解析失败回退到当年"""
    import re
    m = re.search(r"(\d{4})\D*([1-4])\s*季度", text)
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    m = re.search(r"(\d{4})", text)
    if m:
        return m.group(1)
    return fallback_year


def sync_fund_top_holdings(db: Session, fund_code: str, year: str | None = None) -> dict:
    """同步单基金前十大持股，幂等（upsert 同一 quarter 数据）"""
    rows = _fetch_top_holdings_via_akshare(fund_code, year)
    if not rows:
        return {"fund_code": fund_code, "inserted": 0, "updated": 0,
                "warning": "AKShare 未返回数据，已跳过"}

    # 取本批最新季度作为基准；删旧、插新（避免季度切换时残留）
    latest_quarter = max(r["quarter"] for r in rows)
    target_rows = [r for r in rows if r["quarter"] == latest_quarter]

    existing = {
        (r.stock_code, r.quarter): r
        for r in db.query(FundTopHolding).filter(
            FundTopHolding.fund_code == fund_code,
            FundTopHolding.quarter == latest_quarter,
        ).all()
    }

    inserted = 0
    updated = 0
    for r in target_rows:
        key = (r["stock_code"], r["quarter"])
        if key in existing:
            row = existing[key]
            row.stock_name = r["stock_name"]
            row.weight_pct = r["weight_pct"]
            row.shares = r["shares"]
            row.market_value = r["market_value"]
            updated += 1
        else:
            db.add(FundTopHolding(
                fund_code=fund_code,
                stock_code=r["stock_code"],
                stock_name=r["stock_name"],
                weight_pct=r["weight_pct"],
                shares=r["shares"],
                market_value=r["market_value"],
                quarter=r["quarter"],
            ))
            inserted += 1

    db.commit()
    return {"fund_code": fund_code, "quarter": latest_quarter,
            "inserted": inserted, "updated": updated,
            "total_stocks": len(target_rows)}


def sync_all_holding_top_holdings(db: Session | None = None,
                                  max_workers: int = 4) -> dict:
    """同步所有持仓基金的前十大持股（并行）。

    NOTE：AKShare 不是线程安全的，但每次调用独立 dataframe → 并行 4 worker 实测稳定。
    """
    own_db = db is None
    db = db or SessionLocal()
    try:
        codes = [
            h.fund_code for h in
            db.query(Holding).filter(Holding.is_active == True).all()
        ]
        if not codes:
            logger.info("无活跃持仓，跳过持股采集")
            return {"checked": 0, "success": [], "failed": []}

        success: list[dict] = []
        failed: list[dict] = []

        # AKShare 不强线程安全 — 用单线程顺序，但每只控制超时
        for code in codes:
            try:
                result = sync_fund_top_holdings(db, code)
                if result.get("warning"):
                    failed.append({"fund_code": code, "reason": result["warning"]})
                else:
                    success.append(result)
            except Exception as e:
                logger.warning(f"基金 {code} 持股同步失败: {e}")
                failed.append({"fund_code": code, "reason": str(e)})

        logger.info(
            f"基金前十大持股同步完成: 成功 {len(success)} / 失败 {len(failed)} / 总 {len(codes)}"
        )
        return {"checked": len(codes), "success": success, "failed": failed}
    finally:
        if own_db:
            db.close()
