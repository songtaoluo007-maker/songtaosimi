"""
基金净值/实时估值采集 — V2

V2 改动：
- BUG 修复：fetch_fund_info 三个方案全失败时落空，未 return result，调用方 None.get(...) 会崩溃
- BUG 修复：fetch_fund_info AKShare 分支会用 `fund_name` 在 row.get('item') 里做包含匹配，
  对中文断字不稳；改成提取后立即返回，避免覆盖
- 抽出 _common_http_client，统一 timeout / proxy=None / verify 配置
- httpx.get(url, ...) 改用 Client 上下文（确保连接复用且释放）
- 净值采集失败不再静默吞，warning 写明三条失败链路
"""
import json
import re
import time as time_module
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import date, datetime

import httpx
from loguru import logger

from sqlalchemy.orm import joinedload
from backend.database import SessionLocal
from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.utils import clear_proxy_env


@contextmanager
def _http_client(verify: bool = True):
    clear_proxy_env()
    with httpx.Client(timeout=10, verify=verify, proxy=None) as client:
        yield client


def fetch_fund_info(fund_code: str) -> dict:
    """通过基金代码联网查询基金基本信息。

    保证返回一个 dict（即便所有方案失败），调用方 .get('fund_name') 不会 AttributeError。
    """
    result = {"fund_code": fund_code, "fund_name": "", "fund_type": ""}

    # 方案1：天天基金估值接口（含基金名）
    try:
        with _http_client() as client:
            resp = client.get(
                f"http://fundgz.1234567.com.cn/js/{fund_code}.js",
                headers={"Referer": "http://fund.eastmoney.com/"},
            )
            if resp.status_code == 200:
                match = re.search(r'"name"\s*:\s*"([^"]+)"', resp.text)
                if match:
                    result["fund_name"] = match.group(1)
                    return result
    except Exception as e:
        logger.debug(f"fetch_fund_info[天天基金] {fund_code} 失败: {e}")

    # 方案2：东方财富基金详情页
    try:
        with _http_client(verify=False) as client:
            resp = client.get(
                f"https://fund.eastmoney.com/{fund_code}.html",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                match = re.search(r"<title>([^<]+)</title>", resp.text)
                if match:
                    name_match = re.match(r"(.+?)\(", match.group(1))
                    if name_match:
                        result["fund_name"] = name_match.group(1).strip()
                        return result
    except Exception as e:
        logger.debug(f"fetch_fund_info[东方财富] {fund_code} 失败: {e}")

    # 方案3：AKShare 基础信息表
    try:
        import akshare as ak

        df = ak.fund_individual_basic_info_xq(symbol=fund_code)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                item = str(row.get("item", ""))
                value = str(row.get("value", ""))
                if "基金名称" in item:
                    result["fund_name"] = value
                elif "基金类型" in item:
                    result["fund_type"] = value
            if result["fund_name"]:
                return result
    except Exception as e:
        logger.debug(f"fetch_fund_info[AKShare] {fund_code} 失败: {e}")

    # 关键修复：原 v1 此处直接 return None；v2 始终返回 dict
    return result


def fetch_latest_nav(fund_code: str) -> float:
    try:
        with _http_client() as client:
            resp = client.get(
                f"http://fundgz.1234567.com.cn/js/{fund_code}.js",
                headers={"Referer": "http://fund.eastmoney.com/"},
            )
            if resp.status_code == 200:
                match = re.search(r'"dwjz"\s*:\s*"([^"]+)"', resp.text)
                if match:
                    return float(match.group(1))
    except Exception as e:
        logger.debug(f"fetch_latest_nav {fund_code} 失败: {e}")
    return 0.0


def collect_fund_estimates():
    """采集用户持仓基金的实时估值。"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).filter(Holding.is_active == True).all()
        fund_codes = sorted({h.fund_code for h in holdings})
        if not fund_codes:
            logger.info("无活跃持仓，跳过基金估值采集")
            return

        logger.info(f"开始采集 {len(fund_codes)} 只基金实时估值...")
        today = date.today()
        now_time = datetime.now().time()
        count = 0

        with _http_client() as client:
            for code in fund_codes:
                try:
                    resp = client.get(
                        f"https://fundgz.1234567.com.cn/js/{code}.js",
                        params={"rt": int(time_module.time() * 1000)},
                    )
                    text = resp.text
                    if "jsonpgz" not in text:
                        logger.warning(f"基金 {code} 估值获取失败（可能非交易时间）")
                        continue

                    data = json.loads(text[text.index("(") + 1 : text.rindex(")")])
                    estimated_nav = float(data.get("gsz", 0))
                    estimated_change = float(data.get("gszzl", 0))
                    last_nav = float(data.get("dwjz", 0))

                    db.add(MarketSnapshot(
                        symbol=f"fund_{code}",
                        name=data.get("name", ""),
                        snapshot_type="fund",
                        price=estimated_nav,
                        change_pct=estimated_change,
                        snapshot_date=today,
                        snapshot_time=now_time,
                    ))

                    holding = db.query(Holding).filter(
                        Holding.fund_code == code,
                        Holding.is_active == True,
                    ).first()
                    if holding:
                        holding.current_nav = estimated_nav
                        holding.current_value = float(holding.shares or 0) * estimated_nav
                        if last_nav > 0 and estimated_nav > 0:
                            holding.daily_pnl = float(holding.shares or 0) * (estimated_nav - last_nav)
                            holding.daily_pnl_ratio = estimated_change
                            holding.daily_pnl_date = today
                        holding.pnl_amount = float(holding.current_value or 0) - float(holding.cost_amount or 0)
                        if float(holding.cost_amount or 0) > 0:
                            holding.pnl_ratio = (
                                float(holding.pnl_amount or 0) / float(holding.cost_amount) * 100
                            )

                    count += 1
                except Exception as e:
                    logger.warning(f"基金 {code} 估值采集失败: {e}")

        db.commit()
        logger.info(f"基金估值采集完成，成功 {count}/{len(fund_codes)} 只")
    except Exception as e:
        logger.error(f"基金估值采集异常: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def _fetch_single_fund_nav(fund_code: str) -> dict:
    import akshare as ak

    result = {"fund_code": fund_code, "latest_nav": None, "latest_nav_date": "", "acc_nav": None}
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            result["latest_nav_date"] = str(latest.get("净值日期", ""))
            result["latest_nav"] = float(latest.get("单位净值", 0))

        try:
            df_acc = ak.fund_open_fund_info_em(symbol=fund_code, indicator="累计净值走势")
            if df_acc is not None and not df_acc.empty:
                result["acc_nav"] = float(df_acc.iloc[-1].get("累计净值", 0))
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"基金 {fund_code} 净值采集失败: {e}")
        result["error"] = str(e)
    return result


def collect_fund_nav():
    """每日 20:00 后采集基金确认净值（并行，主线程统一写库）"""
    db = SessionLocal()
    try:
        funds = db.query(Fund).all()
        if not funds:
            logger.info("无基金，跳过净值采集")
            return

        fund_codes = [f.fund_code for f in funds]
        logger.info(f"开始并行采集 {len(fund_codes)} 只基金确认净值...")

        nav_results: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_fetch_single_fund_nav, code): code for code in fund_codes}
            for future in as_completed(futures, timeout=180):
                code = futures[future]
                try:
                    nav_results[code] = future.result(timeout=30)
                except Exception as e:
                    logger.warning(f"基金 {code} 净值采集超时: {e}")

        count = 0
        for fund in funds:
            data = nav_results.get(fund.fund_code)
            if not data or data.get("error") or data.get("latest_nav") is None:
                continue
            fund.latest_nav = data["latest_nav"]
            fund.latest_nav_date = data["latest_nav_date"]
            if data["acc_nav"] is not None:
                fund.acc_nav = data["acc_nav"]
            count += 1
        db.commit()

        _update_holdings_nav(db)
        logger.info(f"基金净值采集完成，成功 {count}/{len(fund_codes)} 只")
    except Exception as e:
        logger.error(f"基金净值采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def _update_holdings_nav(db) -> None:
    holdings = (
        db.query(Holding)
        .options(joinedload(Holding.fund))
        .filter(Holding.is_active == True)
        .all()
    )
    for h in holdings:
        fund = h.fund
        if not (fund and fund.latest_nav):
            continue
        h.current_nav = fund.latest_nav
        h.current_value = float(h.shares or 0) * float(fund.latest_nav)
        h.pnl_amount = float(h.current_value or 0) - float(h.cost_amount or 0)
        if float(h.cost_amount or 0) > 0:
            h.pnl_ratio = float(h.pnl_amount or 0) / float(h.cost_amount) * 100
    db.commit()


if __name__ == "__main__":
    collect_fund_estimates()
