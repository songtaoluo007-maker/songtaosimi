"""
定时任务定义
"""
from loguru import logger


def job_collect_a_indices(force=False):
    """A股指数行情采集"""
    from backend.services.market_collector import collect_a_share_indices, is_trading_time, is_trading_day
    if not force:
        if not is_trading_day():
            logger.info("非交易日，跳过A股指数采集")
            return
        if not is_trading_time():
            logger.info("非交易时段，跳过A股指数采集")
            return
    collect_a_share_indices()


def job_collect_sectors(force=False):
    """行业/概念板块采集"""
    from backend.services.market_collector import collect_sectors, is_trading_time, is_trading_day
    if not force:
        if not is_trading_day():
            return
        if not is_trading_time():
            return
    collect_sectors()


def job_collect_concepts(force=False):
    """概念板块采集"""
    from backend.services.market_collector import collect_concepts, is_trading_time, is_trading_day
    if not force:
        if not is_trading_day():
            return
        if not is_trading_time():
            return
    collect_concepts()


def job_collect_fund_estimate():
    """基金盘中估值采集"""
    from backend.services.fund_nav_collector import collect_fund_estimates
    from backend.services.market_collector import is_trading_day
    if not is_trading_day():
        return
    collect_fund_estimates()


def job_collect_fund_nav():
    """基金确认净值采集（每日20:00）"""
    from backend.services.fund_nav_collector import collect_fund_nav
    collect_fund_nav()


def job_collect_global_index():
    """全球指数采集"""
    from backend.services.global_index_collector import collect_global_indices
    collect_global_indices()


def job_collect_news():
    """财经新闻采集"""
    from backend.services.news_collector import collect_news
    collect_news()


def job_calculate_pnl():
    """盈亏计算"""
    from backend.services.pnl_calculator import calculate_pnl
    calculate_pnl()


def job_snapshot_portfolio_daily():
    """每日收盘后保存组合市值快照"""
    from backend.services.return_metrics_v3 import snapshot_portfolio_daily
    snapshot_portfolio_daily()


def job_ai_advice():
    """尾盘AI建议生成 + 飞书推送"""
    from backend.services.market_collector import is_trading_day
    if not is_trading_day():
        logger.info("非交易日，跳过AI建议生成")
        return

    from backend.database import SessionLocal
    from backend.services.ai_advisor import AiAdvisorService
    db = SessionLocal()
    try:
        service = AiAdvisorService(db)
        result = service.generate_close_advice()
        logger.info(f"AI建议生成完成: {result.get('advice_date', 'error')}")
        if result and not result.get("error"):
            from backend.services.notification import send_advice_notification
            send_advice_notification(result)
    except Exception as e:
        logger.error(f"AI建议生成失败: {e}")
    finally:
        db.close()


def job_collect_capital_flows():
    """采集机构/主力资金流向"""
    try:
        from backend.services.capital_flow_collector import collect_all_capital_flows
        collect_all_capital_flows()
    except Exception as e:
        logger.warning(f"资金流向采集任务失败: {e}")


def job_advice_review():
    """AI建议复盘 — 对够天数的未复盘建议批量生成复盘"""
    try:
        from backend.database import SessionLocal
        from backend.services.advice_review_service import batch_review_pending

        db = SessionLocal()
        try:
            result = batch_review_pending(db)
            if result["reviewed"] > 0:
                logger.info(f"AI建议复盘完成: 新增{result['reviewed']}条, 跳过{result['skipped']}条")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"AI建议复盘任务失败: {e}")


def job_sync_fund_managers():
    """P0.2 — 基金经理变更检测（每周日 20:00 跑，高优先级走飞书推送）"""
    try:
        from backend.database import SessionLocal
        from backend.services.fund_manager_service_v3 import sync_all_holding_managers

        db = SessionLocal()
        try:
            result = sync_all_holding_managers(db)
            logger.info(
                f"基金经理同步完成: checked={result.get('checked', 0)} "
                f"high_alerts={result.get('high_alerts_count', 0)} "
                f"skipped={len(result.get('skipped', []))}"
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"基金经理同步任务失败: {e}")


def job_daily_milestone_check():
    """P2.4 — 持仓里程碑/降费档每日检查（每个交易日 9:30 跑）"""
    try:
        from backend.database import SessionLocal
        from backend.services.senior_toolbox_service_v3 import daily_milestone_check

        db = SessionLocal()
        try:
            result = daily_milestone_check(db)
            urgent_count = len(result.get("urgent", []))
            if urgent_count:
                logger.info(f"里程碑检查: {urgent_count} 只持仓近 3 天将降费")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"里程碑检查任务失败: {e}")


def job_monthly_decision_review():
    """P2.2 — 月度决策复盘（每月 1 号 22:00 跑）"""
    try:
        from backend.database import SessionLocal
        from backend.services.decision_review_service_v3 import run_full_review

        db = SessionLocal()
        try:
            result = run_full_review(db)
            logger.info(
                f"月度决策复盘: 新增快照 {result.get('inserted', 0)} / "
                f"回填 30d {result.get('reviewed', 0)} 条"
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"月度决策复盘失败: {e}")


def job_daily_fee_accrual():
    """P2.1 — 每日费率计提（每个交易日 21:00 跑）"""
    try:
        from backend.database import SessionLocal
        from backend.services.fund_fee_service_v3 import daily_fee_accrual

        db = SessionLocal()
        try:
            result = daily_fee_accrual(db)
            logger.info(
                f"费率计提完成: 新增 {result.get('inserted', 0)} / "
                f"更新 {result.get('updated', 0)} / 跳过 {result.get('skipped', 0)}"
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"费率计提任务失败: {e}")


def job_check_investment_plans():
    """P1.1 — 定投到期检查（每个交易日 09:00 跑，触发飞书提醒）"""
    try:
        from backend.database import SessionLocal
        from backend.services.investment_plan_service_v3 import daily_check_and_alert

        db = SessionLocal()
        try:
            result = daily_check_and_alert(db)
            if result.get("checked", 0) > 0:
                logger.info(
                    f"定投到期检查: 今日到期 {result['checked']} 笔，"
                    f"飞书推送 {'成功' if result['notified'] else '跳过'}"
                )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"定投到期检查任务失败: {e}")


def job_sync_fund_top_holdings():
    """P0.3 — 基金前十大持股采集（季报披露后跑）

    触发节奏：每月 5 号 21:00（覆盖 4/8/10/次年 1 月的季报披露窗口）
    """
    try:
        from datetime import date
        from backend.database import SessionLocal
        from backend.services.fund_top_holdings_collector_v3 import sync_all_holding_top_holdings

        # 只在季报披露月份的月初跑（节省 AKShare 调用）
        if date.today().month not in {1, 4, 5, 8, 9, 10, 11}:
            logger.info("非季报披露月，跳过基金持股采集")
            return

        db = SessionLocal()
        try:
            result = sync_all_holding_top_holdings(db)
            logger.info(
                f"基金持股采集完成: success={len(result.get('success', []))} "
                f"failed={len(result.get('failed', []))}"
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"基金持股采集任务失败: {e}")
