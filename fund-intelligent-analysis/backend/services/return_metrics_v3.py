from __future__ import annotations

import math
from datetime import date
from statistics import mean, pstdev

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from backend.database import SessionLocal
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.models.portfolio_snapshot import FundBenchmark, PortfolioDailySnapshot
from backend.models.trade import Trade


def _f(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    return None


def xirr(cash_flows: list[tuple[date, float]]) -> float:
    """Cash-flow weighted annualized return.

    Buy/cost flows are negative, sell/final value flows are positive. The return
    value is a decimal rate, e.g. 0.083 means 8.3%.
    """
    flows = sorted((d, amt) for d, amt in cash_flows if d and amt)
    if len(flows) < 2:
        return 0.0
    if not any(amt < 0 for _, amt in flows) or not any(amt > 0 for _, amt in flows):
        return 0.0

    t0 = flows[0][0]

    def npv(rate: float) -> float:
        return sum(amt / (1 + rate) ** ((d - t0).days / 365.0) for d, amt in flows)

    low, high = -0.9999, 10.0
    low_v, high_v = npv(low), npv(high)
    if low_v == 0:
        return low
    if high_v == 0:
        return high
    if low_v * high_v > 0:
        return 0.0

    for _ in range(120):
        mid = (low + high) / 2
        mid_v = npv(mid)
        if abs(mid_v) < 1e-7:
            return mid
        if low_v * mid_v <= 0:
            high, high_v = mid, mid_v
        else:
            low, low_v = mid, mid_v
    return (low + high) / 2


def calc_max_drawdown(daily_values: list[tuple[date, float]]) -> dict:
    values = sorted((d, v) for d, v in daily_values if d and v is not None)
    if not values:
        return {
            "max_dd": 0.0,
            "peak_date": None,
            "trough_date": None,
            "recovery_days": 0,
            "current_dd": 0.0,
        }

    peak_date, peak_value = values[0]
    max_dd = 0.0
    max_peak_date = peak_date
    max_peak_value = peak_value
    max_trough_date = peak_date
    current_peak = peak_value

    for d, value in values:
        if value > peak_value:
            peak_date, peak_value = d, value
        if value > current_peak:
            current_peak = value
        drawdown = (peak_value - value) / peak_value if peak_value > 0 else 0.0
        if drawdown > max_dd:
            max_dd = drawdown
            max_peak_date = peak_date
            max_peak_value = peak_value
            max_trough_date = d

    recovery_days = 0
    for d, value in values:
        if d >= max_trough_date and value >= max_peak_value:
            recovery_days = (d - max_trough_date).days
            break

    latest_value = values[-1][1]
    current_dd = (current_peak - latest_value) / current_peak if current_peak > 0 else 0.0
    return {
        "max_dd": round(max_dd * 100, 2),
        "peak_date": max_peak_date.isoformat() if max_peak_date else None,
        "trough_date": max_trough_date.isoformat() if max_trough_date else None,
        "recovery_days": recovery_days,
        "current_dd": round(current_dd * 100, 2),
    }


def _holding_cash_flows(db: Session, holding: Holding) -> list[tuple[date, float]]:
    trades = (
        db.query(Trade)
        .filter(Trade.fund_code == holding.fund_code)
        .order_by(Trade.trade_date.asc(), Trade.id.asc())
        .all()
    )
    flows: list[tuple[date, float]] = []
    for t in trades:
        amt = _f(t.amount)
        fee = _f(t.fee)
        if t.trade_type == "买入":
            flows.append((t.trade_date, -(amt + fee)))
        elif t.trade_type == "卖出":
            flows.append((t.trade_date, max(0.0, amt - fee)))

    if not flows and _f(holding.cost_amount) > 0:
        start = _as_date(holding.created_at) or date.today()
        flows.append((start, -_f(holding.cost_amount)))

    if _f(holding.current_value) > 0:
        flows.append((date.today(), _f(holding.current_value)))
    return flows


def calc_holding_xirr(db: Session, holding: Holding) -> float:
    return round(xirr(_holding_cash_flows(db, holding)) * 100, 2)


def calc_portfolio_xirr(db: Session) -> float:
    trades = db.query(Trade).order_by(Trade.trade_date.asc(), Trade.id.asc()).all()
    flows: list[tuple[date, float]] = []
    for t in trades:
        amt = _f(t.amount)
        fee = _f(t.fee)
        if t.trade_type == "买入":
            flows.append((t.trade_date, -(amt + fee)))
        elif t.trade_type == "卖出":
            flows.append((t.trade_date, max(0.0, amt - fee)))

    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    if not flows:
        for h in holdings:
            if _f(h.cost_amount) > 0:
                flows.append((_as_date(h.created_at) or date.today(), -_f(h.cost_amount)))

    total_value = sum(_f(h.current_value) for h in holdings)
    if total_value > 0:
        flows.append((date.today(), total_value))
    return round(xirr(flows) * 100, 2)


def _latest_fund_value_series(db: Session, holding: Holding) -> list[tuple[date, float]]:
    symbol = f"fund_{holding.fund_code}"
    snaps = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.snapshot_type == "fund", MarketSnapshot.symbol == symbol)
        .order_by(MarketSnapshot.snapshot_date.asc(), MarketSnapshot.snapshot_time.asc())
        .all()
    )
    by_day: dict[date, float] = {}
    shares = _f(holding.shares)
    for snap in snaps:
        if snap.snapshot_date:
            by_day[snap.snapshot_date] = shares * _f(snap.price)
    if _f(holding.current_value) > 0:
        by_day[date.today()] = _f(holding.current_value)
    return sorted(by_day.items(), key=lambda item: item[0])


def _portfolio_series_from_snapshots(db: Session) -> list[tuple[date, float]]:
    rows = (
        db.query(PortfolioDailySnapshot)
        .order_by(PortfolioDailySnapshot.snapshot_date.asc())
        .all()
    )
    if rows:
        return [(r.snapshot_date, _f(r.total_value)) for r in rows]

    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    if not holdings:
        return []
    codes = [h.fund_code for h in holdings]
    shares_by_code = {h.fund_code: _f(h.shares) for h in holdings}
    snapshots = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.snapshot_type == "fund",
            MarketSnapshot.symbol.in_([f"fund_{code}" for code in codes]),
        )
        .order_by(MarketSnapshot.snapshot_date.asc(), MarketSnapshot.snapshot_time.asc())
        .all()
    )
    latest_price: dict[str, float] = {}
    values_by_day: dict[date, float] = {}
    for snap in snapshots:
        code = str(snap.symbol).replace("fund_", "")
        latest_price[code] = _f(snap.price)
        values_by_day[snap.snapshot_date] = sum(
            shares_by_code.get(c, 0.0) * latest_price.get(c, 0.0)
            for c in shares_by_code
        )
    current_value = sum(_f(h.current_value) for h in holdings)
    if current_value > 0:
        values_by_day[date.today()] = current_value
    return sorted(values_by_day.items(), key=lambda item: item[0])


def calc_portfolio_drawdown(db: Session) -> dict:
    return calc_max_drawdown(_portfolio_series_from_snapshots(db))


def refresh_holding_metrics(db: Session) -> dict:
    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    per_fund = []
    for h in holdings:
        xirr_pct = calc_holding_xirr(db, h)
        dd = calc_max_drawdown(_latest_fund_value_series(db, h))
        h.xirr = xirr_pct
        h.max_drawdown = dd["max_dd"]
        h.max_drawdown_date = date.fromisoformat(dd["trough_date"]) if dd.get("trough_date") else None
        h.recovery_days = dd["recovery_days"]
        per_fund.append({
            "fund_code": h.fund_code,
            "fund_name": h.fund.fund_name if h.fund else "",
            "xirr": xirr_pct,
            "max_dd": dd["max_dd"],
            "current_dd": dd["current_dd"],
            "peak_date": dd["peak_date"],
            "trough_date": dd["trough_date"],
            "recovery_days": dd["recovery_days"],
        })
    db.commit()
    return {"per_fund": per_fund}


def save_daily_snapshot(snapshot_day: date | None = None, db: Session | None = None) -> dict:
    own_db = db is None
    db = db or SessionLocal()
    try:
        snapshot_day = snapshot_day or date.today()
        holdings = db.query(Holding).filter(Holding.is_active == True).all()
        total_value = sum(_f(h.current_value) for h in holdings)
        total_cost = sum(_f(h.cost_amount) for h in holdings)
        total_pnl = total_value - total_cost
        trades = db.query(Trade).filter(Trade.trade_date == snapshot_day).all()
        cash_flow = sum(
            _f(t.amount) if t.trade_type == "买入" else -_f(t.amount)
            for t in trades
        )

        row = (
            db.query(PortfolioDailySnapshot)
            .filter(PortfolioDailySnapshot.snapshot_date == snapshot_day)
            .first()
        )
        if not row:
            row = PortfolioDailySnapshot(snapshot_date=snapshot_day)
            db.add(row)
        row.total_value = round(total_value, 2)
        row.total_cost = round(total_cost, 2)
        row.total_pnl = round(total_pnl, 2)
        row.cash_flow = round(cash_flow, 2)
        row.note = "收盘后自动快照"
        db.commit()
        return row.to_dict()
    finally:
        if own_db:
            db.close()


def get_xirr_report(db: Session) -> dict:
    refreshed = refresh_holding_metrics(db)
    return {
        "portfolio_xirr": calc_portfolio_xirr(db),
        "per_fund": refreshed["per_fund"],
        "updated_at": date.today().isoformat(),
        "data_note": "XIRR 基于交易现金流；缺少交易记录的老持仓使用当前成本近似。",
    }


def get_drawdown_report(db: Session) -> dict:
    refreshed = refresh_holding_metrics(db)
    return {
        "portfolio": calc_portfolio_drawdown(db),
        "per_fund": refreshed["per_fund"],
        "updated_at": date.today().isoformat(),
        "data_note": "回撤优先使用组合每日快照；快照不足时用本地基金估值快照近似。",
    }


def _return_between(rows: list[tuple[date, float]], start: date, end: date) -> float:
    selected = [(d, v) for d, v in rows if start <= d <= end and v > 0]
    if len(selected) < 2 or selected[0][1] <= 0:
        return 0.0
    return (selected[-1][1] - selected[0][1]) / selected[0][1] * 100


def _daily_returns(rows: list[tuple[date, float]]) -> dict[date, float]:
    result = {}
    previous = None
    for d, value in rows:
        if previous and previous[1] > 0 and value > 0:
            result[d] = (value - previous[1]) / previous[1]
        previous = (d, value)
    return result


def _benchmark_series(db: Session, symbol: str = "000300.SH") -> list[tuple[date, float]]:
    snaps = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.snapshot_type == "index", MarketSnapshot.symbol == symbol)
        .order_by(MarketSnapshot.snapshot_date.asc(), MarketSnapshot.snapshot_time.asc())
        .all()
    )
    by_day: dict[date, float] = {}
    for snap in snaps:
        if snap.snapshot_date:
            by_day[snap.snapshot_date] = _f(snap.price)
    return sorted(by_day.items(), key=lambda item: item[0])


def _beta_and_information_ratio(fund_returns: dict[date, float], bench_returns: dict[date, float]) -> tuple[float | None, float | None]:
    common = sorted(set(fund_returns) & set(bench_returns))
    if len(common) < 3:
        return None, None
    fund_vals = [fund_returns[d] for d in common]
    bench_vals = [bench_returns[d] for d in common]
    bench_mean = mean(bench_vals)
    variance = sum((b - bench_mean) ** 2 for b in bench_vals)
    beta = None if variance == 0 else sum((f - mean(fund_vals)) * (b - bench_mean) for f, b in zip(fund_vals, bench_vals)) / variance
    excess = [f - b for f, b in zip(fund_vals, bench_vals)]
    tracking_error = pstdev(excess)
    info_ratio = None if tracking_error == 0 else mean(excess) / tracking_error * math.sqrt(252)
    return (
        round(beta, 3) if beta is not None else None,
        round(info_ratio, 3) if info_ratio is not None else None,
    )


def get_benchmark_compare_report(db: Session) -> dict:
    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
    benchmark_rows = _benchmark_series(db)
    per_fund = []
    for h in holdings:
        benchmark = (
            db.query(FundBenchmark)
            .filter(FundBenchmark.fund_code == h.fund_code, FundBenchmark.is_primary == True)
            .first()
        )
        bench_symbol = benchmark.benchmark_symbol if benchmark else "000300.SH"
        bench_name = benchmark.benchmark_name if benchmark else "沪深300"
        bench_rows = benchmark_rows if bench_symbol == "000300.SH" else _benchmark_series(db, bench_symbol)
        fund_rows = _latest_fund_value_series(db, h)
        if fund_rows:
            start, end = fund_rows[0][0], fund_rows[-1][0]
        else:
            start = end = date.today()
        fund_return = _return_between(fund_rows, start, end)
        benchmark_return = _return_between(bench_rows, start, end)
        beta, info_ratio = _beta_and_information_ratio(_daily_returns(fund_rows), _daily_returns(bench_rows))
        per_fund.append({
            "fund_code": h.fund_code,
            "fund_name": h.fund.fund_name if h.fund else "",
            "fund_return": round(fund_return, 2),
            "benchmark_return": round(benchmark_return, 2),
            "alpha": round(fund_return - benchmark_return, 2),
            "beta": beta,
            "information_ratio": info_ratio,
            "benchmark_symbol": bench_symbol,
            "benchmark_name": bench_name,
        })
    return {"per_fund": per_fund, "updated_at": date.today().isoformat()}


def snapshot_portfolio_daily() -> None:
    try:
        result = save_daily_snapshot()
        logger.info(f"组合每日快照已保存: {result.get('snapshot_date')}")
    except Exception as exc:
        logger.warning(f"组合每日快照保存失败: {exc}")
