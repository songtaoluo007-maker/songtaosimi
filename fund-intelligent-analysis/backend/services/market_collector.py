"""
A股行情采集服务
使用新浪Finance API采集沪深指数、行业板块实时行情，AKShare作为备用
"""
import os
import traceback
from datetime import date, datetime, time
from loguru import logger

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models.market_snapshot import MarketSnapshot


def _clear_proxy_env():
    """清除可能干扰网络请求的代理环境变量，包括Windows系统代理"""
    for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
        os.environ.pop(key, None)
    # 设置 NO_PROXY=* 让 requests/urllib3 跳过 Windows 系统代理
    os.environ['NO_PROXY'] = '*'
    os.environ['no_proxy'] = '*'


def _decode_market_text(resp) -> str:
    """新浪行情常用GBK，显式解码避免中文板块/指数名称变成乱码。"""
    try:
        return resp.content.decode("gbk", errors="ignore")
    except Exception:
        return resp.text


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _money_to_yuan(value) -> float:
    """AKShare资金流接口的净额单位通常为亿元，板块异动为元。"""
    amount = _to_float(value)
    if abs(amount) < 100000:
        return amount * 100000000
    return amount


# 新浪Finance指数代码映射：新浪代码 -> (symbol, name)
# 使用完整格式(sh000001)而非简化格式(s_sh000001)以获取OHLC数据
SINA_INDEX_MAP = {
    "sh000001": ("000001.SH", "上证指数"),
    "sz399001": ("399001.SZ", "深证成指"),
    "sz399006": ("399006.SZ", "创业板指"),
    "sh000300": ("000300.SH", "沪深300"),
    "sh000905": ("000905.SH", "中证500"),
    "sh000016": ("000016.SH", "上证50"),
}


# 关注的主要指数代码（AKShare备用）
MAJOR_INDICES = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000300": "沪深300",
    "000905": "中证500",
    "000016": "上证50",
}


def is_trading_time() -> bool:
    """判断当前是否在A股交易时段"""
    now = datetime.now()
    current_time = now.time()

    # 上午 09:30-11:30
    if time(9, 30) <= current_time <= time(11, 30):
        return True
    # 下午 13:00-15:00
    if time(13, 0) <= current_time <= time(15, 0):
        return True
    return False


def is_trading_day() -> bool:
    """判断今天是否为A股交易日。

    不在服务进程内调用 AKShare 交易日历；该路径会间接加载 py_mini_racer，
    在部分 Windows Python 环境中可能触发原生崩溃。
    """
    today = date.today()
    if today.weekday() >= 5:
        return False
    # 常用法定节假日/调休闭市日期；未知年份退化为工作日判断。
    cn_market_holidays = {
        # 2026 元旦、春节、清明、劳动节、端午、中秋国庆
        "2026-01-01",
        "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
        "2026-04-06",
        "2026-05-01", "2026-05-04", "2026-05-05",
        "2026-06-19",
        "2026-09-25",
        "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",
    }
    return today.strftime("%Y-%m-%d") not in cn_market_holidays


def collect_a_share_indices():
    """采集A股主要指数行情，优先使用新浪Finance API"""
    _clear_proxy_env()
    db = SessionLocal()
    try:
        logger.info("开始采集A股指数行情...")
        today = date.today()
        now_time = datetime.now().time()
        count = 0

        # 方案一：新浪Finance API
        try:
            count = _collect_indices_sina(db, today, now_time)
        except Exception as e:
            logger.warning(f"新浪API采集A股指数失败，尝试AKShare: {e}")
            # 方案二：AKShare备用
            try:
                count = _collect_indices_akshare(db, today, now_time)
            except Exception as e2:
                logger.error(f"AKShare备用方案也失败: {e2}")

        db.commit()
        logger.info(f"A股指数行情采集完成，共 {count} 条记录")

    except Exception as e:
        logger.error(f"A股指数行情采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def _collect_indices_sina(db, today, now_time) -> int:
    """通过新浪Finance API采集A股指数"""
    import httpx
    import re

    sina_codes = ",".join(SINA_INDEX_MAP.keys())
    url = f"https://hq.sinajs.cn/list={sina_codes}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn",
    }
    resp = httpx.get(url, headers=headers, timeout=15, proxy=None)
    resp.raise_for_status()

    count = 0
    # 解析完整格式: var hq_str_sh000001="上证指数,开盘价,昨收,当前价,最高,最低,买一,卖一,成交量,成交额,...";
    for line in _decode_market_text(resp).strip().split("\n"):
        line = line.strip()
        if not line or '=""' in line:
            continue
        match = re.match(r'var hq_str_(\w+)="([^"]+)"', line)
        if not match:
            continue
        sina_code = match.group(1)
        data_str = match.group(2)
        parts = data_str.split(",")
        if len(parts) < 6 or sina_code not in SINA_INDEX_MAP:
            continue

        symbol, _ = SINA_INDEX_MAP[sina_code]
        name = parts[0]
        open_price = float(parts[1]) if parts[1] else 0
        prev_close = float(parts[2]) if parts[2] else 0
        price = float(parts[3]) if parts[3] else 0
        high = float(parts[4]) if parts[4] else 0
        low = float(parts[5]) if parts[5] else 0
        volume = int(parts[8]) if len(parts) > 8 and parts[8] else 0
        turnover = float(parts[9]) if len(parts) > 9 and parts[9] else 0

        # 计算涨跌额和涨跌幅
        change_amount = round(price - prev_close, 4) if prev_close else 0
        change_pct = round((price - prev_close) / prev_close * 100, 4) if prev_close else 0

        snapshot = MarketSnapshot(
            symbol=symbol,
            name=name,
            snapshot_type="index",
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            volume=volume,
            turnover=turnover,
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
        raise ValueError("新浪API返回数据为空")
    return count


def _collect_indices_akshare(db, today, now_time) -> int:
    """通过AKShare采集A股指数（备用）"""
    import akshare as ak

    df_sh = ak.stock_zh_index_spot_em(symbol="上证系列指数")
    df_sz = ak.stock_zh_index_spot_em(symbol="深证系列指数")

    count = 0
    for df in [df_sh, df_sz]:
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            if code not in MAJOR_INDICES:
                continue
            snapshot = MarketSnapshot(
                symbol=f"{code}.SH" if code.startswith("000") else f"{code}.SZ",
                name=str(row.get("名称", "")),
                snapshot_type="index",
                price=row.get("最新价", 0),
                change_pct=row.get("涨跌幅", 0),
                change_amount=row.get("涨跌额", 0),
                volume=int(row.get("成交量", 0)) if row.get("成交量") else 0,
                turnover=row.get("成交额", 0),
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


def collect_sectors():
    """采集行业板块行情，优先使用新浪Finance API"""
    _clear_proxy_env()
    db = SessionLocal()
    try:
        logger.info("开始采集板块行情...")
        today = date.today()
        now_time = datetime.now().time()
        count = 0

        # 方案一：新浪行业板块
        try:
            count = _collect_sectors_sina(db, today, now_time)
        except Exception as e:
            logger.warning(f"新浪API采集板块失败，尝试AKShare: {e}")
            # 方案二：AKShare备用
            try:
                count = _collect_sectors_akshare(db, today, now_time)
            except Exception as e2:
                logger.error(f"AKShare备用方案也失败: {e2}")

        db.commit()
        logger.info(f"板块行情采集完成，共 {count} 条记录")

    except Exception as e:
        logger.error(f"板块行情采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def collect_concepts():
    """采集概念板块行情"""
    _clear_proxy_env()
    db = SessionLocal()
    try:
        logger.info("开始采集概念板块行情...")
        today = date.today()
        now_time = datetime.now().time()
        count = 0
        try:
            import akshare as ak
            df = ak.stock_board_concept_name_em()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    snapshot = MarketSnapshot(
                        symbol=str(row.get("板块代码", "")),
                        name=str(row.get("板块名称", "")),
                        snapshot_type="concept",
                        price=row.get("最新价", 0) or 0,
                        change_pct=row.get("涨跌幅", 0) or 0,
                        change_amount=row.get("涨跌额", 0) or 0,
                        turnover=row.get("成交额", 0) or 0,
                        snapshot_date=today,
                        snapshot_time=now_time,
                    )
                    db.add(snapshot)
                    count += 1
        except Exception as e:
            logger.warning(f"概念板块采集失败: {e}")

        if count == 0:
            try:
                import akshare as ak
                df = ak.stock_board_concept_name_ths()
                if df is not None and not df.empty:
                    for idx, row in df.iterrows():
                        price = 0
                        change_pct = 0
                        turnover = 0
                        if idx < 60:
                            try:
                                hist = ak.stock_board_concept_index_ths(symbol=str(row.get("name", "")))
                                if hist is not None and len(hist) >= 2:
                                    last = hist.iloc[-1]
                                    prev = hist.iloc[-2]
                                    price = float(last.get("收盘价", 0) or 0)
                                    prev_close = float(prev.get("收盘价", 0) or 0)
                                    turnover = float(last.get("成交额", 0) or 0)
                                    change_pct = (price - prev_close) / prev_close * 100 if prev_close else 0
                            except Exception:
                                pass
                        snapshot = MarketSnapshot(
                            symbol=str(row.get("code", "")),
                            name=str(row.get("name", "")),
                            snapshot_type="concept",
                            price=price,
                            change_pct=change_pct,
                            change_amount=0,
                            turnover=turnover,
                            snapshot_date=today,
                            snapshot_time=now_time,
                        )
                        db.add(snapshot)
                        count += 1
            except Exception as e:
                logger.warning(f"同花顺概念板块备用采集失败: {e}")
        db.commit()
        logger.info(f"概念板块行情采集完成，共 {count} 条记录")
    except Exception as e:
        logger.error(f"概念板块行情采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def _collect_sectors_sina(db, today, now_time) -> int:
    """通过新浪Finance API采集行业板块"""
    import httpx
    import re
    import json

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn",
    }

    # 获取新浪行业板块列表
    url = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
    resp = httpx.get(url, headers=headers, timeout=15, proxy=None)
    resp.raise_for_status()

    # 解析格式: var S_Finance_bankuai_sinaindustry = {"new_blhy":"new_blhy,玻璃行业,...",...}
    text = _decode_market_text(resp).strip()
    match = re.search(r'=\s*(\{.+\})\s*;?$', text)
    if not match:
        raise ValueError("无法解析新浪行业板块JSON")

    data = json.loads(match.group(1))
    count = 0
    for code, info_str in data.items():
        parts = info_str.split(",")
        if len(parts) < 5:
            continue
        # 格式: code,名称,股票数,均价,涨跌额,涨跌幅,成交量,成交额,...
        name = parts[1]
        try:
            change_pct = float(parts[5]) if len(parts) > 5 and parts[5] else 0
            avg_price = float(parts[3]) if parts[3] else 0
            turnover = float(parts[7]) if len(parts) > 7 and parts[7] else 0
        except (ValueError, IndexError):
            change_pct = 0
            avg_price = 0
            turnover = 0

        snapshot = MarketSnapshot(
            symbol=code,
            name=name,
            snapshot_type="sector",
            price=avg_price,
            change_pct=change_pct,
            change_amount=0,
            turnover=turnover,
            snapshot_date=today,
            snapshot_time=now_time,
        )
        db.add(snapshot)
        count += 1

    if count == 0:
        raise ValueError("新浪板块采集无数据")
    return count


def _collect_sectors_akshare(db, today, now_time) -> int:
    """通过AKShare采集板块（备用）"""
    import akshare as ak
    count = 0

    try:
        df_industry = ak.stock_board_industry_name_em()
        if df_industry is not None and not df_industry.empty:
            for _, row in df_industry.iterrows():
                snapshot = MarketSnapshot(
                    symbol=str(row.get("板块代码", "")),
                    name=str(row.get("板块名称", "")),
                    snapshot_type="sector",
                    price=row.get("最新价", 0),
                    change_pct=row.get("涨跌幅", 0),
                    change_amount=row.get("涨跌额", 0),
                    turnover=row.get("成交额", 0),
                    snapshot_date=today,
                    snapshot_time=now_time,
                )
                db.add(snapshot)
                count += 1
    except Exception as e:
        logger.warning(f"行业板块采集失败: {e}")

    return count


def get_board_rankings(snapshot_type: str = "sector", limit: int = 20) -> dict:
    """Return live heat and main-capital rankings for industry/concept boards."""
    _clear_proxy_env()
    import akshare as ak

    trading_day = is_trading_day()
    latest_label = "交易日" if trading_day else "最近交易日"

    flow_func = ak.stock_fund_flow_concept if snapshot_type == "concept" else ak.stock_fund_flow_industry
    flow_df = flow_func(symbol="即时")
    heat_df = None
    try:
        heat_df = ak.stock_board_change_em()
    except Exception as e:
        logger.warning(f"板块异动热度获取失败，使用资金流热度替代: {e}")

    heat_map = {}
    if heat_df is not None and not heat_df.empty:
        for _, row in heat_df.iterrows():
            name = str(row.get("板块名称", ""))
            if not name:
                continue
            heat_map[name] = {
                "heat_score": _to_float(row.get("板块异动总次数")),
                "main_net_inflow": _money_to_yuan(row.get("主力净流入")),
            }

    rows = []
    if flow_df is not None and not flow_df.empty:
        for _, row in flow_df.iterrows():
            name = str(row.get("行业", ""))
            if not name:
                continue
            heat = heat_map.get(name, {})
            net_inflow = _money_to_yuan(row.get("净额"))
            heat_score = heat.get("heat_score") or (
                abs(net_inflow) / 100000000 + abs(_to_float(row.get("行业-涨跌幅"))) * 10 + _to_float(row.get("公司家数"))
            )
            rows.append({
                "symbol": name,
                "name": name,
                "snapshot_type": snapshot_type,
                "price": _to_float(row.get("行业指数") or row.get("当前价")),
                "change_pct": _to_float(row.get("行业-涨跌幅")),
                "turnover": _money_to_yuan(row.get("流入资金")) + _money_to_yuan(row.get("流出资金")),
                "main_net_inflow": net_inflow,
                "capital_inflow": _money_to_yuan(row.get("流入资金")),
                "capital_outflow": _money_to_yuan(row.get("流出资金")),
                "company_count": int(_to_float(row.get("公司家数"))),
                "leading_stock": str(row.get("领涨股", "")),
                "leading_stock_change_pct": _to_float(row.get("领涨股-涨跌幅")),
                "heat_score": heat_score,
                "source": "akshare_live",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

    heat_top = sorted(rows, key=lambda item: item.get("heat_score", 0), reverse=True)[:limit]
    inflow_top = sorted(rows, key=lambda item: item.get("main_net_inflow", 0), reverse=True)[:limit]
    for idx, row in enumerate(heat_top, start=1):
        row["heat_rank"] = idx
    for idx, row in enumerate(inflow_top, start=1):
        row["inflow_rank"] = idx

    return {
        "snapshot_type": snapshot_type,
        "heat_top": heat_top,
        "inflow_top": inflow_top,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_trading_day": trading_day,
        "board_data_label": latest_label,
        "market_date_label": "今日交易日" if trading_day else "休市期间，展示最近交易日数据",
        "source": "akshare_live",
    }


if __name__ == "__main__":
    collect_a_share_indices()
    collect_sectors()
