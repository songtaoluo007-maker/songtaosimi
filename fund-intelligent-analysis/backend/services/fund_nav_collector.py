"""
基金净值和实时估值采集服务
使用AKShare + 东方财富基金估值API
"""
import json
import os
import re
import time as time_module
import traceback
from datetime import date, datetime

import httpx
from loguru import logger

from backend.database import SessionLocal
from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot


def fetch_fund_info(fund_code: str) -> dict:
    """通过基金代码联网查询基金基本信息"""
    # 清除代理
    for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
        os.environ.pop(key, None)
    os.environ['NO_PROXY'] = '*'

    result = {"fund_code": fund_code, "fund_name": "", "fund_type": ""}

    # 方案1: 天天基金估值接口
    try:
        url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
        with httpx.Client(timeout=10, proxy=None) as client:
            resp = client.get(url, headers={"Referer": "http://fund.eastmoney.com/"})
            if resp.status_code == 200:
                text = resp.text
                match = re.search(r'"name"\s*:\s*"([^"]+)"', text)
                if match:
                    result["fund_name"] = match.group(1)
                    return result
    except Exception:
        pass

    # 方案2: 东方财富基金详情页
    try:
        url = f"https://fund.eastmoney.com/{fund_code}.html"
        with httpx.Client(timeout=10, verify=False, proxy=None) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                match = re.search(r'<title>([^<]+)</title>', resp.text)
                if match:
                    title = match.group(1)
                    name_match = re.match(r'(.+?)\(', title)
                    if name_match:
                        result["fund_name"] = name_match.group(1).strip()
                        return result
    except Exception:
        pass

    # 方案3: 尝试 AKShare
    try:
        import akshare as ak
        df = ak.fund_individual_basic_info_xq(symbol=fund_code)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                if '基金名称' in str(row.get('item', '')):
                    result["fund_name"] = str(row.get('value', ''))
                elif '基金类型' in str(row.get('item', '')):
                    result["fund_type"] = str(row.get('value', ''))
            if result["fund_name"]:
                return result
    except Exception:
        pass

    return result


def fetch_latest_nav(fund_code: str) -> float:
    """查询基金最新净值"""
    try:
        url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
        with httpx.Client(timeout=10, proxy=None) as client:
            resp = client.get(url, headers={"Referer": "http://fund.eastmoney.com/"})
            if resp.status_code == 200:
                match = re.search(r'"dwjz"\s*:\s*"([^"]+)"', resp.text)
                if match:
                    return float(match.group(1))
    except Exception:
        pass
    return 0.0


def collect_fund_estimates():
    """采集用户持仓基金的实时估值"""
    db = SessionLocal()
    try:
        # 获取所有活跃持仓的基金代码
        holdings = db.query(Holding).filter(Holding.is_active == True).all()
        fund_codes = list(set(h.fund_code for h in holdings))

        if not fund_codes:
            logger.info("无活跃持仓，跳过基金估值采集")
            return

        logger.info(f"开始采集 {len(fund_codes)} 只基金实时估值...")

        today = date.today()
        now_time = datetime.now().time()
        count = 0

        for code in fund_codes:
            try:
                url = f"https://fundgz.1234567.com.cn/js/{code}.js"
                resp = httpx.get(url, params={"rt": int(time_module.time() * 1000)}, timeout=10)
                text = resp.text

                if "jsonpgz" not in text:
                    logger.warning(f"基金 {code} 估值获取失败，可能非交易时间")
                    continue

                json_str = text[text.index("(") + 1 : text.rindex(")")]
                data = json.loads(json_str)

                estimated_nav = float(data.get("gsz", 0))
                estimated_change = float(data.get("gszzl", 0))
                last_nav = float(data.get("dwjz", 0))

                # 保存估值快照
                snapshot = MarketSnapshot(
                    symbol=f"fund_{code}",
                    name=data.get("name", ""),
                    snapshot_type="fund",
                    price=estimated_nav,
                    change_pct=estimated_change,
                    snapshot_date=today,
                    snapshot_time=now_time,
                )
                db.add(snapshot)

                # 更新持仓的当前净值和市值
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
                        holding.pnl_ratio = float(holding.pnl_amount or 0) / float(holding.cost_amount) * 100

                count += 1

            except Exception as e:
                logger.warning(f"基金 {code} 估值采集失败: {e}")
                continue

        db.commit()
        logger.info(f"基金估值采集完成，成功 {count}/{len(fund_codes)} 只")

    except Exception as e:
        logger.error(f"基金估值采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def collect_fund_nav():
    """采集基金确认净值（每日20:00后）"""
    db = SessionLocal()
    try:
        import akshare as ak

        # 获取所有基金
        funds = db.query(Fund).all()
        if not funds:
            logger.info("无基金，跳过净值采集")
            return

        logger.info(f"开始采集 {len(funds)} 只基金确认净值...")

        for fund in funds:
            try:
                df = ak.fund_open_fund_info_em(symbol=fund.fund_code, indicator="单位净值走势")
                if df is None or df.empty:
                    continue

                latest = df.iloc[-1]
                nav_date = latest.get("净值日期", "")
                nav_value = float(latest.get("单位净值", 0))

                fund.latest_nav = nav_value
                fund.latest_nav_date = nav_date

                # 获取累计净值
                try:
                    df_acc = ak.fund_open_fund_info_em(symbol=fund.fund_code, indicator="累计净值走势")
                    if df_acc is not None and not df_acc.empty:
                        fund.acc_nav = float(df_acc.iloc[-1].get("累计净值", 0))
                except Exception:
                    pass

            except Exception as e:
                logger.warning(f"基金 {fund.fund_code} 净值采集失败: {e}")
                continue

        db.commit()

        # 更新持仓的当前净值
        _update_holdings_nav(db)

        logger.info("基金净值采集完成")

    except Exception as e:
        logger.error(f"基金净值采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


def _update_holdings_nav(db: SessionLocal):
    """用最新净值更新所有持仓的市值和盈亏"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    for h in holdings:
        fund = db.query(Fund).filter(Fund.fund_code == h.fund_code).first()
        if fund and fund.latest_nav:
            h.current_nav = fund.latest_nav
            h.current_value = float(h.shares or 0) * float(fund.latest_nav)
            h.pnl_amount = float(h.current_value or 0) - float(h.cost_amount or 0)
            if float(h.cost_amount or 0) > 0:
                h.pnl_ratio = float(h.pnl_amount or 0) / float(h.cost_amount) * 100
    db.commit()


if __name__ == "__main__":
    collect_fund_estimates()
