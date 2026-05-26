"""
全球指数采集服务
"""
import traceback
from datetime import date, datetime
from loguru import logger

from backend.database import SessionLocal
from backend.models.market_snapshot import MarketSnapshot
from backend.utils import clear_proxy_env as _clear_proxy_env


# 新浪Finance全球指数代码映射：新浪代码 -> (symbol, name)
SINA_GLOBAL_MAP = {
    "int_dji": ("DJI", "道琼斯"),
    "int_nasdaq": ("IXIC", "纳斯达克"),
    "int_sp500": ("SPX", "标普500"),
    "int_hangseng": ("HSI", "恒生指数"),
    "int_nikkei": ("N225", "日经225"),
    "b_FTSE": ("FTSE", "英国富时100"),
    "b_DAX": ("DAX", "德国DAX30"),
    "b_FCHI": ("FCHI", "法国CAC40"),
    "b_KS11": ("KS11", "韩国KOSPI"),
}


# 关注的全球指数（AKShare备用）
GLOBAL_INDICES = {
    "道琼斯": "DJI",
    "标普500": "SPX",
    "纳斯达克": "IXIC",
    "恒生指数": "HSI",
    "日经225": "N225",
    "英国富时100": "FTSE",
    "德国DAX30": "DAX",
    "法国CAC40": "FCHI",
    "韩国KOSPI": "KS11",
}


def collect_global_indices():
    """采集全球主要指数，优先使用新浪Finance API"""
    _clear_proxy_env()
    db = SessionLocal()
    try:
        logger.info("开始采集全球指数...")
        today = date.today()
        now_time = datetime.now().time()
        count = 0

        # 方案一：新浪Finance API
        try:
            count = _collect_global_sina(db, today, now_time)
        except Exception as e:
            logger.warning(f"新浪API采集全球指数失败，尝试AKShare: {e}")
            # 方案二：AKShare备用
            try:
                count = _collect_global_akshare(db, today, now_time)
            except Exception as e2:
                logger.error(f"AKShare备用方案也失败: {e2}")

        db.commit()
        logger.info(f"全球指数采集完成，共 {count} 条记录")

    except Exception as e:
        logger.error(f"全球指数采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def _collect_global_sina(db, today, now_time) -> int:
    """通过新浪Finance API采集全球指数"""
    import httpx
    import re

    sina_codes = ",".join(SINA_GLOBAL_MAP.keys())
    url = f"https://hq.sinajs.cn/list={sina_codes}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn",
    }
    resp = httpx.get(url, headers=headers, timeout=15, proxy=None)
    resp.raise_for_status()

    count = 0
    for line in resp.text.strip().split("\n"):
        line = line.strip()
        if not line or '=""' in line:
            continue
        match = re.match(r'var hq_str_(\w+)="([^"]+)"', line)
        if not match:
            continue
        sina_code = match.group(1)
        data_str = match.group(2)
        parts = data_str.split(",")
        if len(parts) < 3 or sina_code not in SINA_GLOBAL_MAP:
            continue

        symbol, default_name = SINA_GLOBAL_MAP[sina_code]
        name = parts[0] if parts[0] else default_name
        price = float(parts[1]) if len(parts) > 1 and parts[1] else 0
        change_amount = float(parts[2]) if len(parts) > 2 and parts[2] else 0
        change_pct = float(parts[3]) if len(parts) > 3 and parts[3] else 0

        # b_ 前缀的指数包含OHLC数据（位置8-11）
        open_price = 0
        prev_close = 0
        high = 0
        low = 0
        if sina_code.startswith("b_") and len(parts) > 11:
            open_price = float(parts[8]) if parts[8] else 0
            prev_close = float(parts[9]) if parts[9] else 0
            high = float(parts[10]) if parts[10] else 0
            low = float(parts[11]) if parts[11] else 0

        snapshot = MarketSnapshot(
            symbol=symbol,
            name=name,
            snapshot_type="global",
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            high=high,
            low=low,
            open=open_price,
            prev_close=prev_close,
            snapshot_date=today,
            snapshot_time=now_time,
        )
        db.add(snapshot)
        count += 1

    if count == 0:
        raise ValueError("新浪API返回全球指数数据为空")
    return count


def _collect_global_akshare(db, today, now_time) -> int:
    """通过AKShare采集全球指数（备用）"""
    import akshare as ak

    df = ak.index_global_spot_em()
    if df is None or df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        name = str(row.get("名称", ""))
        if name not in GLOBAL_INDICES:
            continue
        symbol = GLOBAL_INDICES[name]
        snapshot = MarketSnapshot(
            symbol=symbol,
            name=name,
            snapshot_type="global",
            price=row.get("最新价", 0),
            change_pct=row.get("涨跌幅", 0),
            change_amount=row.get("涨跌额", 0),
            high=row.get("最高", 0) or 0,
            low=row.get("最低", 0) or 0,
            open=row.get("今开", 0) or 0,
            prev_close=row.get("昨收", 0) or 0,
            snapshot_date=today,
            snapshot_time=now_time,
        )
        db.add(snapshot)
        count += 1
    return count


if __name__ == "__main__":
    collect_global_indices()
