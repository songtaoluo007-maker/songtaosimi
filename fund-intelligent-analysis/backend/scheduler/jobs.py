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


def job_ai_advice():
    """尾盘AI建议生成"""
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
    except Exception as e:
        logger.error(f"AI建议生成失败: {e}")
    finally:
        db.close()


def job_update_holdings_nav():
    """更新持仓净值+市值"""
    from backend.services.fund_nav_collector import collect_fund_nav
    collect_fund_nav()
