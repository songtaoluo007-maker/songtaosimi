"""
机构/主力/大户资金流向采集服务
覆盖：北向资金、主力资金流向、融资融券、龙虎榜机构席位
"""
import traceback
from datetime import date, datetime, timedelta

import pandas as pd
from loguru import logger

from backend.database import SessionLocal
from backend.models.capital_flow import CapitalFlow
from backend.utils import clear_proxy_env, to_float


def _latest_trading_day() -> date:
    """最近的交易日：周一至周五为当天，周六周日为上个周五"""
    today = date.today()
    if today.weekday() == 5:      # 周六 → 周五
        return today - timedelta(days=1)
    elif today.weekday() == 6:    # 周日 → 周五
        return today - timedelta(days=2)
    return today


def collect_north_bound_flow():
    """采集北向资金（沪深港通）净流入"""
    clear_proxy_env()
    db = SessionLocal()
    try:
        import akshare as ak
        today = _latest_trading_day()

        # 北向资金汇总 — stock_hsgt_fund_flow_summary_em
        try:
            df = ak.stock_hsgt_fund_flow_summary_em()
            if df is not None and not df.empty:
                # 实际列名: 交易日, 类型, 板块, 资金方向, 成交净买额, 资金净流入
                today_str = today.strftime("%Y-%m-%d")
                today_rows = df[df["交易日"].astype(str).str[:10] == today_str]
                if today_rows.empty:
                    today_rows = df.tail(5)  # 兜底取最近数据

                # 只取北向（沪股通/深股通方向）
                north_rows = today_rows[today_rows["资金方向"] == "北向"]
                total_net = 0.0
                total_buy = 0.0
                total_sell = 0.0
                for _, row in north_rows.iterrows():
                    net = to_float(row.get("成交净买额", 0))
                    inflow = to_float(row.get("资金净流入", 0))
                    total_net += net or inflow
                    total_buy += to_float(row.get("当日资金余额", 0)) or 0

                # 分市场明细
                for _, row in north_rows.iterrows():
                    name = str(row.get("板块", ""))
                    if "沪" in name or "深" in name:
                        net = to_float(row.get("成交净买额", 0)) or to_float(row.get("资金净流入", 0))
                        db.add(CapitalFlow(
                            flow_date=today, flow_type="north_bound",
                            symbol=name, name=name,
                            net_inflow=net,
                            buy_amount=to_float(row.get("当日资金余额", 0)) or 0,
                        ))

                # 汇总
                db.add(CapitalFlow(
                    flow_date=today, flow_type="north_bound",
                    symbol="north", name="北向资金",
                    net_inflow=total_net,
                    buy_amount=total_buy,
                ))
                logger.info(f"北向资金汇总: 净流入={total_net:.1f}亿")
        except Exception as e:
            logger.warning(f"北向资金汇总采集失败: {e}")

        db.commit()
        logger.info("北向资金采集完成")
    except Exception as e:
        logger.error(f"北向资金采集失败: {e}\n{traceback.format_exc()}")
        db.rollback()
    finally:
        db.close()


def _col_value(row, *keys):
    """安全取值 — 尝试多个列名直到找到有效值"""
    for k in keys:
        v = row.get(k)
        if v is not None and str(v) not in ('nan', 'None', ''):
            return to_float(v)
    return 0.0


def collect_main_force_flow():
    """采集全市场主力资金流向（超大单/大单/中单/小单）+ 行业板块"""
    clear_proxy_env()
    db = SessionLocal()
    try:
        import akshare as ak
        today = _latest_trading_day()

        # A股全市场资金流向 — stock_market_fund_flow
        # 实际列名: 日期, 主力净流入-净额, 超大单净流入-净额, 大单净流入-净额, ...
        try:
            df = ak.stock_market_fund_flow()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                super_large = _col_value(latest, "超大单净流入-净额", "超大单净额")
                large = _col_value(latest, "大单净流入-净额", "大单净额")
                medium = _col_value(latest, "中单净流入-净额", "中单净额")
                small = _col_value(latest, "小单净流入-净额", "小单净额")
                main_net = super_large + large

                db.add(CapitalFlow(
                    flow_date=today, flow_type="main_force",
                    symbol="all", name="全市场",
                    super_large_net=super_large / 1e8,
                    large_net=large / 1e8,
                    medium_net=medium / 1e8,
                    small_net=small / 1e8,
                    net_inflow=main_net / 1e8,
                ))
                logger.info(f"全市场主力资金: 净流入={main_net/1e8:.1f}亿（超大单{super_large/1e8:.1f} 大单{large/1e8:.1f}）")
        except Exception as e:
            logger.warning(f"全市场主力资金采集失败: {e}")

        # 行业板块主力资金 — stock_sector_fund_flow_rank
        # 实际列名: 序号, 名称, 今日涨跌幅, 主力净流入-净额, 超大单净流入-净额, ...
        for indicator in ["今日", "3日", "5日"]:
            try:
                sector_df = ak.stock_sector_fund_flow_rank(indicator=indicator)
                if sector_df is not None and not sector_df.empty:
                    top_in = sector_df.nlargest(5, "主力净流入-净额" if "主力净流入-净额" in sector_df.columns else sector_df.columns[3])
                    top_out = sector_df.nsmallest(5, "主力净流入-净额" if "主力净流入-净额" in sector_df.columns else sector_df.columns[3])
                    for _, row in pd.concat([top_in, top_out]).iterrows():
                        name = str(row.get("名称", row.get("板块", row.get("行业", ""))))
                        if not name or name in ("None", "nan"):
                            continue
                        net = _col_value(row, "主力净流入-净额", "主力净流入", "净流入")
                        db.add(CapitalFlow(
                            flow_date=today, flow_type="main_force",
                            symbol=name, name=name,
                            net_inflow=net / 1e8 if abs(net) > 10000 else net,
                            buy_amount=to_float(row.get("今日涨跌幅", 0)),
                        ))
                    logger.info(f"行业资金流采集成功 indicator={indicator}, sectors={len(sector_df)}")
                    break
            except Exception as e:
                logger.debug(f"行业资金流 indicator={indicator} 失败: {e}")

        db.commit()
        logger.info("主力资金流向采集完成")
    except Exception as e:
        logger.error(f"主力资金采集失败: {e}\n{traceback.format_exc()}")
        db.rollback()
    finally:
        db.close()


def collect_margin_data():
    """采集融资融券余额"""
    clear_proxy_env()
    db = SessionLocal()
    try:
        import akshare as ak
        today = _latest_trading_day()
        # 尝试最近5个交易日
        for days_back in range(5):
            try:
                target = today - timedelta(days=days_back)
                df = ak.stock_margin_detail_sse(date=target.strftime("%Y%m%d"))
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    db.add(CapitalFlow(
                        flow_date=today, flow_type="margin",
                        symbol="sse", name="融资融券",
                        margin_balance=to_float(latest.get("融资余额", 0)) / 1e8,
                        short_balance=to_float(latest.get("融券余额", 0)) / 1e8,
                    ))
                    logger.info(f"融资融券采集成功 date={target}")
                    break
            except Exception as e:
                logger.debug(f"采集重试跳过: {e}")
                continue
        db.commit()
    except Exception as e:
        logger.warning(f"融资融券采集失败: {e}")
    finally:
        db.close()


def collect_lhb_institution():
    """采集龙虎榜机构席位买卖"""
    clear_proxy_env()
    db = SessionLocal()
    try:
        import akshare as ak
        today = _latest_trading_day()
        # 尝试最近5个交易日
        for days_back in range(5):
            try:
                target = today - timedelta(days=days_back)
                df = ak.stock_lhb_detail_daily_sina(date=target.strftime("%Y-%m-%d"))
                if df is not None and not df.empty:
                    inst_buy = 0.0
                    inst_sell = 0.0
                    for _, row in df.iterrows():
                        seat = str(row.get("营业部名称", ""))
                        if "机构" in seat:
                            inst_buy += to_float(row.get("买入额", 0)) / 1e8
                            inst_sell += to_float(row.get("卖出额", 0)) / 1e8
                    if inst_buy > 0 or inst_sell > 0:
                        db.add(CapitalFlow(
                            flow_date=today, flow_type="lhb",
                            symbol="all", name="龙虎榜机构席位",
                            institution_buy=inst_buy,
                            institution_sell=inst_sell,
                            net_inflow=inst_buy - inst_sell,
                        ))
                    logger.info(f"龙虎榜采集成功 date={target} buy={inst_buy:.1f} sell={inst_sell:.1f}")
                    break
            except Exception as e:
                logger.debug(f"采集重试跳过: {e}")
                continue
        db.commit()
    except Exception as e:
        logger.warning(f"龙虎榜采集失败: {e}")
    finally:
        db.close()


def _national_team_keywords():
    """国家队/知名机构关键词"""
    return [
        "中信证券", "中信建投", "中金公司", "华泰证券", "国泰君安",
        "海通证券", "招商证券", "广发证券", "申万宏源",
        "汇金", "证金", "社保基金", "养老金", "中央结算",
        "瑞银", "摩根", "高盛", "花旗", "美林", "野村",
    ]


def collect_national_team_flow():
    """采集机构动向：龙虎榜机构席位明细（今日）+ 机构追踪汇总"""
    clear_proxy_env()
    db = SessionLocal()
    try:
        import akshare as ak
        today = _latest_trading_day()

        # --- 机构席位买卖明细（今日，stock_lhb_jgmx_sina） ---
        # 列: 股票代码, 股票名称, 交易日期, 机构席位买入额(万元), 机构席位卖出额(万元), 类型
        try:
            df_mx = ak.stock_lhb_jgmx_sina()
            if df_mx is not None and not df_mx.empty:
                today_str = today.strftime("%Y-%m-%d")
                today_rows = df_mx[df_mx["交易日期"].astype(str).str[:10] == today_str]
                if today_rows.empty:
                    today_rows = df_mx

                inst_total_buy = inst_total_sell = 0.0
                stock_count = 0
                for _, row in today_rows.iterrows():
                    stock = str(row.get("股票名称", ""))
                    buy = to_float(row.get("机构席位买入额", 0)) / 1e4  # 万元→亿
                    sell = to_float(row.get("机构席位卖出额", 0)) / 1e4
                    if not stock or (buy == 0 and sell == 0):
                        continue

                    db.add(CapitalFlow(
                        flow_date=today, flow_type="lhb",
                        symbol=stock, name=stock,
                        institution_buy=buy,
                        institution_sell=sell,
                        net_inflow=buy - sell,
                    ))
                    inst_total_buy += buy
                    inst_total_sell += sell
                    stock_count += 1

                # 汇总
                db.add(CapitalFlow(
                    flow_date=today, flow_type="lhb",
                    symbol="all", name="龙虎榜机构席位",
                    institution_buy=inst_total_buy,
                    institution_sell=inst_total_sell,
                    net_inflow=inst_total_buy - inst_total_sell,
                ))
                logger.info(f"机构席位明细采集: {stock_count}只票 buy={inst_total_buy:.1f}亿 sell={inst_total_sell:.1f}亿")
        except Exception as e:
            logger.warning(f"机构席位明细采集失败: {e}")

        # --- 机构追踪汇总（累积数据） ---
        try:
            df_zz = ak.stock_lhb_jgzz_sina()
            if df_zz is not None and not df_zz.empty:
                for _, row in df_zz.head(30).iterrows():
                    stock = str(row.get("股票名称", ""))
                    cum_buy = to_float(row.get("累积买入额", 0)) / 1e4
                    cum_sell = to_float(row.get("累积卖出额", 0)) / 1e4
                    net = to_float(row.get("净额", 0)) / 1e4
                    if not stock:
                        continue

                    db.add(CapitalFlow(
                        flow_date=today, flow_type="lhb_track",
                        symbol=str(row.get("股票代码", "")),
                        name=stock,
                        institution_buy=cum_buy,
                        institution_sell=cum_sell,
                        net_inflow=net,
                        buy_amount=to_float(row.get("买入次数", 0)),
                        sell_amount=to_float(row.get("卖出次数", 0)),
                    ))
                logger.info(f"机构追踪汇总采集: {len(df_zz)}条")
        except Exception as e:
            logger.warning(f"机构追踪汇总采集失败: {e}")

        db.commit()
        logger.info("国家队/机构资金采集完成")
    except Exception as e:
        logger.error(f"国家队采集失败: {e}\n{traceback.format_exc()}")
        db.rollback()
    finally:
        db.close()


def collect_all_capital_flows():
    """一键采集所有资金流向数据"""
    logger.info("开始采集资金流向数据...")
    # 清除今日旧数据避免重复
    db = SessionLocal()
    try:
        today = _latest_trading_day()
        db.query(CapitalFlow).filter(CapitalFlow.flow_date == today).delete()
        db.commit()
    except Exception as e:
        logger.debug(f"清除资金流向旧数据跳过: {e}")
    finally:
        db.close()

    collect_north_bound_flow()
    collect_main_force_flow()
    collect_margin_data()
    collect_lhb_institution()
    collect_national_team_flow()
    logger.info("资金流向数据采集全部完成")


def get_capital_flow_summary(db: SessionLocal = None) -> str:
    """生成资金流向文本摘要，供 AI 建议使用"""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        today = _latest_trading_day()
        flows = db.query(CapitalFlow).filter(
            CapitalFlow.flow_date == today
        ).all()

        if not flows:
            # 尝试最近交易日
            latest_date = db.query(CapitalFlow.flow_date).order_by(
                CapitalFlow.flow_date.desc()
            ).first()
            if latest_date:
                flows = db.query(CapitalFlow).filter(
                    CapitalFlow.flow_date == latest_date[0]
                ).all()

        if not flows:
            return "暂无资金流向数据"

        lines = ["【资金流向数据】"]
        nb_total = sum(f.net_inflow or 0 for f in flows if f.flow_type == "north_bound")
        if nb_total != 0:
            direction = "大幅流入" if nb_total > 50 else ("流入" if nb_total > 0 else "流出")
            lines.append(f"北向资金{abs(nb_total):.1f}亿，{direction}")

        mf_all = [f for f in flows if f.flow_type == "main_force" and f.symbol == "all"]
        for mf in mf_all:
            main_force = float(mf.super_large_net or 0) + float(mf.large_net or 0)
            if main_force != 0:
                d = "主力抢筹" if main_force > 0 else "主力出逃"
                lines.append(f"主力资金（超大单+大单）净{'流入' if main_force > 0 else '流出'}{abs(main_force):.1f}亿，{d}")

        mf_sectors = [f for f in flows if f.flow_type == "main_force" and f.symbol != "all" and abs(float(f.net_inflow or 0)) > 0]
        if mf_sectors:
            top_in = sorted(mf_sectors, key=lambda x: float(x.net_inflow or 0), reverse=True)[:3]
            top_out = sorted(mf_sectors, key=lambda x: float(x.net_inflow or 0))[:3]
            lines.append("行业主力净流入TOP3: " + ", ".join(
                f"{f.name}(+{float(f.net_inflow or 0):.1f}亿)" for f in top_in if float(f.net_inflow or 0) > 0
            ) or "无")
            lines.append("行业主力净流出TOP3: " + ", ".join(
                f"{f.name}({float(f.net_inflow or 0):.1f}亿)" for f in top_out if float(f.net_inflow or 0) < 0
            ) or "无")

        lhb = [f for f in flows if f.flow_type == "lhb"]
        for l in lhb:
            if float(l.institution_buy or 0) > 0:
                lines.append(f"龙虎榜机构席位买入{float(l.institution_buy):.1f}亿，卖出{float(l.institution_sell):.1f}亿，净{'买入' if float(l.net_inflow or 0) > 0 else '卖出'}{abs(float(l.net_inflow or 0)):.1f}亿")

        margin = [f for f in flows if f.flow_type == "margin"]
        for m in margin:
            lines.append(f"融资余额{float(m.margin_balance or 0):.1f}亿，融券余额{float(m.short_balance or 0):.1f}亿")

        return "\n".join(lines) + "\n\n分析要求：请将以上资金流向作为判断市场情绪和板块方向的重要参考，结合北向、主力和机构动向，对你的加减仓建议进行加权调整。主力大幅流入的板块可适度提高加仓置信度；主力持续流出的板块应降低仓位或保持观望。"
    finally:
        if own_db and db:
            db.close()
