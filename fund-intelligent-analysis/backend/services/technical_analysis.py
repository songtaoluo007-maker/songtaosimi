from __future__ import annotations

import os
import json
import re
from datetime import date, datetime, timedelta
from typing import Any


def clear_proxy_env():
    for key in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def ema(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (span + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def sma(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            result.append(None)
        else:
            result.append(round(sum(values[idx + 1 - window: idx + 1]) / window, 4))
    return result


def enrich_indicators(rows: list[dict]) -> list[dict]:
    closes = [to_float(row.get("close")) for row in rows]
    highs = [to_float(row.get("high")) for row in rows]
    lows = [to_float(row.get("low")) for row in rows]
    volumes = [to_float(row.get("volume")) for row in rows]

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = [a - b for a, b in zip(ema12, ema26)]
    dea = ema(dif, 9)
    macd = [(d - e) * 2 for d, e in zip(dif, dea)]

    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    vol_ma5 = sma(volumes, 5)

    k_values: list[float] = []
    d_values: list[float] = []
    last_k = 50.0
    last_d = 50.0
    for idx, close in enumerate(closes):
        start = max(0, idx - 8)
        high_n = max(highs[start: idx + 1]) if highs[start: idx + 1] else close
        low_n = min(lows[start: idx + 1]) if lows[start: idx + 1] else close
        rsv = 50 if high_n == low_n else (close - low_n) / (high_n - low_n) * 100
        last_k = last_k * 2 / 3 + rsv / 3
        last_d = last_d * 2 / 3 + last_k / 3
        k_values.append(last_k)
        d_values.append(last_d)

    gains: list[float] = [0]
    losses: list[float] = [0]
    for idx in range(1, len(closes)):
        delta = closes[idx] - closes[idx - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    avg_gain = sma(gains, 14)
    avg_loss = sma(losses, 14)

    for idx, row in enumerate(rows):
        loss = avg_loss[idx] or 0
        gain = avg_gain[idx] or 0
        rsi = 100 if loss == 0 and gain > 0 else (50 if loss == 0 else 100 - 100 / (1 + gain / loss))
        vol_base = vol_ma5[idx] or 0
        row["ma5"] = ma5[idx]
        row["ma10"] = ma10[idx]
        row["ma20"] = ma20[idx]
        row["ma60"] = ma60[idx]
        row["dif"] = round(dif[idx], 4) if idx < len(dif) else None
        row["dea"] = round(dea[idx], 4) if idx < len(dea) else None
        row["macd"] = round(macd[idx], 4) if idx < len(macd) else None
        row["kdj_k"] = round(k_values[idx], 2)
        row["kdj_d"] = round(d_values[idx], 2)
        row["kdj_j"] = round(3 * k_values[idx] - 2 * d_values[idx], 2)
        row["rsi14"] = round(rsi, 2)
        row["volume_ratio"] = round(row.get("volume", 0) / vol_base, 2) if vol_base else None
    return rows


def enrich_intraday(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    prices = [to_float(row.get("price")) for row in rows]
    volumes = [to_float(row.get("volume")) for row in rows]
    avg_prices: list[float] = []
    cumulative_value = 0.0
    cumulative_volume = 0.0
    prev_price = prices[0] if prices else 0
    vol_ma5 = sma(volumes, 5)
    for idx, row in enumerate(rows):
        price = prices[idx]
        volume = volumes[idx]
        turnover = to_float(row.get("turnover"))
        cumulative_volume += volume
        cumulative_value += turnover if turnover else price * volume
        supplied_avg = to_float(row.get("avg_price"))
        row["avg_price"] = supplied_avg if supplied_avg else (round(cumulative_value / cumulative_volume, 4) if cumulative_volume else price)
        row["change_amount"] = round(price - prev_price, 4) if prev_price else 0
        row["change_pct"] = round((price - prev_price) / prev_price * 100, 4) if prev_price else 0
        row["volume_ratio"] = round(volume / vol_ma5[idx], 2) if vol_ma5[idx] else None
    return rows


def normalize_hist_df(df, limit: int) -> list[dict]:
    rows: list[dict] = []
    if df is None or df.empty:
        return rows
    df = df.tail(limit)
    for _, row in df.iterrows():
        rows.append({
            "date": str(row.get("日期") or row.get("date") or row.get("时间") or ""),
            "open": to_float(row.get("开盘") or row.get("开盘价") or row.get("open")),
            "close": to_float(row.get("收盘") or row.get("收盘价") or row.get("close") or row.get("最新价")),
            "high": to_float(row.get("最高") or row.get("最高价") or row.get("high")),
            "low": to_float(row.get("最低") or row.get("最低价") or row.get("low")),
            "volume": to_float(row.get("成交量") or row.get("volume")),
            "turnover": to_float(row.get("成交额") or row.get("turnover")),
            "change_pct": to_float(row.get("涨跌幅") or row.get("change_pct")),
            "amplitude": to_float(row.get("振幅")),
        })
    return enrich_indicators(rows)


def normalize_ohlc_df(df, limit: int) -> list[dict]:
    """Normalize Sina global/HK/US index frames with English OHLC columns."""
    rows: list[dict] = []
    if df is None or df.empty:
        return rows
    df = df.tail(limit)
    prev_close = 0.0
    for _, row in df.iterrows():
        close = to_float(row.get("close"))
        open_price = to_float(row.get("open"))
        amount = to_float(row.get("amount"))
        rows.append({
            "date": str(row.get("date") or ""),
            "open": open_price,
            "close": close,
            "high": to_float(row.get("high")),
            "low": to_float(row.get("low")),
            "volume": to_float(row.get("volume")),
            "turnover": amount,
            "prev_close": prev_close or open_price,
            "change_pct": (close - prev_close) / prev_close * 100 if prev_close else 0,
            "change_amount": close - prev_close if prev_close else 0,
        })
        prev_close = close
    return enrich_indicators(rows)


def index_code(symbol: str) -> str:
    return symbol.split(".")[0].replace("fund_", "")


def index_secid(symbol: str) -> str:
    code = index_code(symbol)
    market = "1" if symbol.endswith(".SH") or code.startswith("000") else "0"
    return f"{market}.{code}"


def sina_symbol(symbol: str) -> str:
    code = index_code(symbol)
    return f"sh{code}" if symbol.endswith(".SH") or code.startswith("000") else f"sz{code}"


def aggregate_rows(rows: list[dict], period: str, limit: int) -> list[dict]:
    if period == "daily":
        return enrich_indicators(rows[-limit:])
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        try:
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        key = f"{d.isocalendar().year}-{d.isocalendar().week:02d}" if period == "weekly" else f"{d.year}-{d.month:02d}"
        buckets.setdefault(key, []).append(row)
    agg: list[dict] = []
    for items in buckets.values():
        first = items[0]
        last = items[-1]
        prev_close = to_float(first.get("prev_close") or first.get("open"))
        close = to_float(last.get("close"))
        agg.append({
            "date": last["date"],
            "open": to_float(first.get("open")),
            "close": close,
            "high": max(to_float(i.get("high")) for i in items),
            "low": min(to_float(i.get("low")) for i in items),
            "volume": sum(to_float(i.get("volume")) for i in items),
            "turnover": sum(to_float(i.get("turnover")) for i in items),
            "change_pct": (close - prev_close) / prev_close * 100 if prev_close else 0,
            "change_amount": close - prev_close if prev_close else 0,
        })
    return enrich_indicators(agg[-limit:])


GLOBAL_US_SINA = {
    "DJI": ".DJI",
    "IXIC": ".IXIC",
    "SPX": ".INX",
}

GLOBAL_HK_SINA = {
    "HSI": "HSI",
}

GLOBAL_SINA_NAMES = {
    "N225": "日经225指数",
    "FTSE": "英国富时100指数",
    "DAX": "德国DAX 30种股价指数",
    "FCHI": "法CAC40指数",
    "KS11": "首尔综合指数",
}


def fetch_index_history_sina(symbol: str, period: str, limit: int) -> list[dict]:
    clear_proxy_env()
    import requests

    datalen = max(limit * 8, 260) if period != "daily" else max(limit, 120)
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": sina_symbol(symbol), "scale": "240", "ma": "no", "datalen": str(datalen)}
    resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    rows: list[dict] = []
    prev_close = 0.0
    for item in data:
        close = to_float(item.get("close"))
        open_price = to_float(item.get("open"))
        rows.append({
            "date": str(item.get("day") or ""),
            "open": open_price,
            "close": close,
            "high": to_float(item.get("high")),
            "low": to_float(item.get("low")),
            "volume": to_float(item.get("volume")),
            "turnover": 0,
            "prev_close": prev_close or open_price,
            "change_pct": (close - prev_close) / prev_close * 100 if prev_close else 0,
            "change_amount": close - prev_close if prev_close else 0,
        })
        prev_close = close
    return aggregate_rows(rows, period, limit)


def fetch_index_intraday_sina(symbol: str) -> list[dict]:
    clear_proxy_env()
    import requests

    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": sina_symbol(symbol), "scale": "5", "ma": "no", "datalen": "80"}
    resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return []
    rows: list[dict] = []
    for item in data[-80:]:
        rows.append({
            "time": str(item.get("day") or ""),
            "price": to_float(item.get("close")),
            "avg_price": 0,
            "volume": to_float(item.get("volume")),
            "turnover": 0,
        })
    return enrich_intraday(rows)


def fetch_index_history_em(symbol: str, period: str, limit: int) -> list[dict]:
    clear_proxy_env()
    import httpx

    klt = {"daily": "101", "weekly": "102", "monthly": "103"}.get(period, "101")
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": index_secid(symbol),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": klt,
        "fqt": "0",
        "beg": "0",
        "end": "20500101",
        "lmt": str(limit),
    }
    with httpx.Client(timeout=20, proxy=None, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        data = client.get(url, params=params).json()
    klines = (data.get("data") or {}).get("klines") or []
    rows: list[dict] = []
    for item in klines[-limit:]:
        parts = item.split(",")
        if len(parts) < 11:
            continue
        rows.append({
            "date": parts[0],
            "open": to_float(parts[1]),
            "close": to_float(parts[2]),
            "high": to_float(parts[3]),
            "low": to_float(parts[4]),
            "volume": to_float(parts[5]),
            "turnover": to_float(parts[6]),
            "amplitude": to_float(parts[7]),
            "change_pct": to_float(parts[8]),
            "change_amount": to_float(parts[9]),
            "turnover_rate": to_float(parts[10]),
        })
    return enrich_indicators(rows)


def fetch_index_intraday_em(symbol: str) -> list[dict]:
    clear_proxy_env()
    import httpx

    url = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
    params = {
        "secid": index_secid(symbol),
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "ndays": "1",
    }
    with httpx.Client(timeout=20, proxy=None, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        data = client.get(url, params=params).json()
    trends = (data.get("data") or {}).get("trends") or []
    rows: list[dict] = []
    for item in trends[-300:]:
        parts = item.split(",")
        if len(parts) < 6:
            continue
        rows.append({
            "time": parts[0],
            "price": to_float(parts[2]),
            "avg_price": to_float(parts[3]),
            "volume": to_float(parts[5]),
            "turnover": to_float(parts[6]) if len(parts) > 6 else 0,
        })
    return enrich_intraday(rows)


def fetch_index_history(symbol: str, period: str, limit: int) -> list[dict]:
    direct_error = None
    try:
        rows = fetch_index_history_em(symbol, period, limit)
        if rows:
            return rows
    except Exception as e:
        direct_error = e

    sina_error = None
    try:
        rows = fetch_index_history_sina(symbol, period, limit)
        if rows:
            return rows
    except Exception as e:
        sina_error = e

    try:
        clear_proxy_env()
        import akshare as ak
        code = index_code(symbol)
        end = date.today()
        start = end - timedelta(days=max(limit * 3, 120))
        ak_period = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}.get(period, "daily")
        df = ak.index_zh_a_hist(
            symbol=code,
            period=ak_period,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
        return normalize_hist_df(df, limit)
    except Exception as e:
        raise RuntimeError(f"东方财富直连失败: {direct_error}; 新浪历史失败: {sina_error}; AKShare失败: {e}")


def fetch_index_intraday(symbol: str) -> list[dict]:
    direct_error = None
    try:
        rows = fetch_index_intraday_em(symbol)
        if rows:
            return rows
    except Exception as e:
        direct_error = e

    sina_error = None
    try:
        rows = fetch_index_intraday_sina(symbol)
        if rows:
            return rows
    except Exception as e:
        sina_error = e

    try:
        clear_proxy_env()
        import akshare as ak
        code = index_code(symbol)
        df = ak.index_zh_a_hist_min_em(symbol=code, period="1")
        rows = []
        if df is None or df.empty:
            return rows
        for _, row in df.tail(300).iterrows():
            rows.append({
                "time": str(row.get("时间") or row.get("日期") or ""),
                "price": to_float(row.get("收盘") or row.get("最新价")),
                "volume": to_float(row.get("成交量")),
                "turnover": to_float(row.get("成交额")),
            })
        return enrich_intraday(rows)
    except Exception as e:
        raise RuntimeError(f"东方财富分时直连失败: {direct_error}; 新浪分时失败: {sina_error}; AKShare失败: {e}")


def fetch_global_history(symbol: str, name: str, period: str, limit: int) -> list[dict]:
    """Fetch global index K-line data from stable Sina-backed AKShare endpoints."""
    clear_proxy_env()
    import akshare as ak

    code = symbol.upper()
    daily_rows: list[dict] = []
    if code in GLOBAL_US_SINA:
        df = ak.index_us_stock_sina(symbol=GLOBAL_US_SINA[code])
        daily_rows = normalize_ohlc_df(df, max(limit * 8, 500))
    elif code in GLOBAL_HK_SINA:
        df = ak.stock_hk_index_daily_sina(symbol=GLOBAL_HK_SINA[code])
        daily_rows = normalize_ohlc_df(df, max(limit * 8, 500))
    else:
        lookup_name = GLOBAL_SINA_NAMES.get(code, name)
        df = ak.index_global_hist_sina(symbol=lookup_name)
        daily_rows = normalize_ohlc_df(df, max(limit * 8, 500))

    return aggregate_rows(daily_rows, period, limit)


def fetch_global_intraday(symbol: str, name: str) -> list[dict]:
    # Most free global endpoints only expose delayed daily bars. Return the latest
    # daily closes as a usable preview instead of an empty chart.
    rows = fetch_global_history(symbol, name, "daily", 80)
    return enrich_intraday([
        {
            "time": row["date"],
            "price": row["close"],
            "avg_price": row.get("ma5") or row["close"],
            "volume": row.get("volume", 0),
            "turnover": row.get("turnover", 0),
        }
        for row in rows
    ])


def fetch_board_history(name: str, board_type: str, period: str, limit: int) -> list[dict]:
    clear_proxy_env()
    import akshare as ak

    end = date.today()
    start = end - timedelta(days=max(limit * 3, 120))
    period_map = {"daily": "日k", "weekly": "周k", "monthly": "月k"}
    ak_period = period_map.get(period, "日k")
    used_daily_fallback = False
    try:
        func = ak.stock_board_concept_hist_em if board_type == "concept" else ak.stock_board_industry_hist_em
        df = func(symbol=name, period=ak_period, start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
    except Exception:
        used_daily_fallback = True
        func = ak.stock_board_concept_index_ths if board_type == "concept" else ak.stock_board_industry_index_ths
        df = func(symbol=name)
    rows = normalize_hist_df(df, max(limit * 8, 300) if used_daily_fallback else limit)
    rows = append_board_live_quote(rows, name, board_type)
    if used_daily_fallback and period != "daily":
        return aggregate_rows(rows, period, limit)
    return enrich_indicators(rows[-limit:])


def fetch_board_intraday(name: str, board_type: str) -> list[dict]:
    clear_proxy_env()
    import akshare as ak

    func = ak.stock_board_concept_hist_min_em if board_type == "concept" else ak.stock_board_industry_hist_min_em
    try:
        df = func(symbol=name, period="1")
    except Exception:
        daily_rows = fetch_board_history(name, board_type, "daily", 80)
        return enrich_intraday([
            {
                "time": row["date"],
                "price": row["close"],
                "avg_price": row.get("ma5") or row["close"],
                "volume": row.get("volume", 0),
                "turnover": row.get("turnover", 0),
            }
            for row in daily_rows
        ])
    rows = []
    if df is None or df.empty:
        return rows
    for _, row in df.tail(300).iterrows():
        rows.append({
            "time": str(row.get("时间") or row.get("日期") or ""),
            "price": to_float(row.get("收盘") or row.get("最新价")),
            "volume": to_float(row.get("成交量")),
            "turnover": to_float(row.get("成交额")),
        })
    return enrich_intraday(rows)


def append_board_live_quote(rows: list[dict], name: str, board_type: str) -> list[dict]:
    """Append today's live board quote from fund-flow data when history source lags."""
    try:
        clear_proxy_env()
        import akshare as ak

        flow_func = ak.stock_fund_flow_concept if board_type == "concept" else ak.stock_fund_flow_industry
        df = flow_func(symbol="即时")
        if df is None or df.empty:
            return rows
        matched = df[df["行业"].astype(str) == name]
        if matched.empty:
            return rows
        row = matched.iloc[0]
        today = date.today().strftime("%Y-%m-%d")
        price = to_float(row.get("行业指数") or row.get("当前价"))
        change_pct = to_float(row.get("行业-涨跌幅"))
        prev_close = price / (1 + change_pct / 100) if change_pct != -100 else price
        live = {
            "date": today,
            "open": prev_close,
            "close": price,
            "high": max(price, prev_close),
            "low": min(price, prev_close),
            "volume": 0,
            "turnover": (to_float(row.get("流入资金")) + to_float(row.get("流出资金"))) * 100000000,
            "change_pct": change_pct,
            "change_amount": price - prev_close,
            "prev_close": prev_close,
        }
        if rows and rows[-1].get("date") == today:
            rows[-1].update(live)
        else:
            rows.append(live)
    except Exception:
        return rows
    return rows
