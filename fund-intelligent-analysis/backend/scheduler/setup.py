"""
APScheduler调度器初始化与注册
"""
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from backend.config import settings

_scheduler = None
_job_status = {}
# 长任务专用线程池，避免 AI 建议/复盘阻塞短采集任务
_long_task_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scheduler-long-")


def _run_in_long_pool(fn):
    """将任务提交到长任务线程池执行，不阻塞调度器主循环。"""
    _long_task_executor.submit(_wrap_long_task, fn)


def _wrap_long_task(fn):
    try:
        fn()
    except Exception:
        logger.exception(f"长任务执行异常")


def init_scheduler():
    """初始化并启动调度器"""
    global _scheduler

    _scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    from backend.scheduler.jobs import (
        job_collect_a_indices,
        job_collect_sectors,
        job_collect_concepts,
        job_collect_fund_estimate,
        job_collect_fund_nav,
        job_collect_global_index,
        job_collect_news,
        job_calculate_pnl,
        job_snapshot_portfolio_daily,
        job_ai_advice,
        job_collect_capital_flows,
        job_advice_review,
        job_sync_fund_managers,
        job_sync_fund_top_holdings,
        job_check_investment_plans,
        job_daily_fee_accrual,
        job_monthly_decision_review,
    )

    # A股指数行情 - 交易时间每5分钟
    _scheduler.add_job(
        job_collect_a_indices, CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*/5"),
        id="collect_a_indices", name="A股指数行情",
    )

    # 行业板块 - 交易时间每10分钟
    _scheduler.add_job(
        job_collect_sectors, CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*/10"),
        id="collect_sectors", name="行业板块行情",
    )

    _scheduler.add_job(
        job_collect_concepts, CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*/15"),
        id="collect_concepts", name="概念板块行情",
    )

    # 基金盘中估值 - 交易时间每30分钟
    _scheduler.add_job(
        job_collect_fund_estimate, CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*/30"),
        id="collect_fund_estimate", name="基金盘中估值",
    )

    # 基金确认净值 - 每日20:00
    _scheduler.add_job(
        job_collect_fund_nav, CronTrigger(hour=20, minute=0),
        id="collect_fund_nav", name="基金确认净值",
    )

    # 全球指数 - 每日08:00和20:00
    _scheduler.add_job(
        job_collect_global_index, CronTrigger(hour="8,20", minute=0),
        id="collect_global_index", name="全球指数",
    )

    # 财经新闻 - 盘前、午间、尾盘前、盘后
    _scheduler.add_job(
        job_collect_news, CronTrigger(hour="7,12,14,18", minute="0,25"),
        id="collect_news", name="财经新闻",
    )

    # 盈亏计算 - 每日15:10和20:30
    _scheduler.add_job(
        job_calculate_pnl, CronTrigger(hour="15,20", minute="10,30"),
        id="calculate_pnl", name="盈亏计算",
    )

    # 组合每日快照 - 每个交易日收盘后，用于最大回撤计算
    _scheduler.add_job(
        job_snapshot_portfolio_daily, CronTrigger(day_of_week="mon-fri", hour=15, minute=35),
        id="snapshot_portfolio_daily", name="组合每日快照",
    )

    # AI尾盘建议 - 默认每个交易日14:30，收盘前最后半小时（长任务线程池）
    def _trigger_ai_advice():
        _run_in_long_pool(job_ai_advice)

    _scheduler.add_job(
        _trigger_ai_advice,
        CronTrigger(day_of_week="mon-fri", hour=settings.AI_ADVICE_HOUR, minute=settings.AI_ADVICE_MINUTE),
        id="ai_advice", name="AI尾盘持仓建议",
    )

    # 机构/主力资金流向 - 交易时间每30分钟
    _scheduler.add_job(
        job_collect_capital_flows,
        CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*/30"),
        id="collect_capital_flows", name="机构主力资金流向",
    )

    # AI建议复盘 — 每个交易日 15:30 执行（长任务线程池）
    def _trigger_advice_review():
        _run_in_long_pool(job_advice_review)

    _scheduler.add_job(
        _trigger_advice_review,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30),
        id="advice_review", name="AI建议复盘",
    )

    # P0.2 — 基金经理变更检测：每周日 20:00（长任务线程池，避免阻塞调度器主循环）
    def _trigger_manager_sync():
        _run_in_long_pool(job_sync_fund_managers)

    _scheduler.add_job(
        _trigger_manager_sync,
        CronTrigger(day_of_week="sun", hour=20, minute=0),
        id="sync_fund_managers", name="基金经理变更检测",
    )

    # P0.3 — 基金前十大持股采集：每月 5 号 21:00（仅季报披露窗口月份执行）
    def _trigger_top_holdings_sync():
        _run_in_long_pool(job_sync_fund_top_holdings)

    _scheduler.add_job(
        _trigger_top_holdings_sync,
        CronTrigger(day="5", hour=21, minute=0),
        id="sync_fund_top_holdings", name="基金前十大持股采集",
    )

    # P1.1 — 定投到期检查：每日 09:00（短任务）
    _scheduler.add_job(
        job_check_investment_plans,
        CronTrigger(hour=9, minute=0),
        id="check_investment_plans", name="定投到期检查",
    )

    # P2.1 — 每日费率计提：每个交易日 21:00（短任务）
    _scheduler.add_job(
        job_daily_fee_accrual,
        CronTrigger(day_of_week="mon-fri", hour=21, minute=0),
        id="daily_fee_accrual", name="每日费率计提",
    )

    # P2.2 — 月度决策复盘：每月 1 号 22:00（长任务）
    def _trigger_monthly_review():
        _run_in_long_pool(job_monthly_decision_review)

    _scheduler.add_job(
        _trigger_monthly_review,
        CronTrigger(day="1", hour=22, minute=0),
        id="monthly_decision_review", name="月度决策复盘",
    )

    _scheduler.start()
    logger.info("调度器已启动，共注册 {} 个定时任务".format(len(_scheduler.get_jobs())))

    # 记录状态
    for job in _scheduler.get_jobs():
        _job_status[job.id] = {
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
        }


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler, _long_task_executor
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("调度器已关闭")
    if _long_task_executor:
        _long_task_executor.shutdown(wait=True, cancel_futures=True)
        logger.info("长任务线程池已关闭")


def get_scheduler_status() -> dict:
    """获取调度器状态"""
    if not _scheduler:
        return {"status": "not_running", "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
            "pending": job.pending,
        })

    return {
        "status": "running",
        "job_count": len(jobs),
        "jobs": jobs,
    }


def trigger_job_now(job_id: str) -> dict:
    """手动触发某个定时任务"""
    if not _scheduler:
        return {"error": "调度器未运行"}

    job = _scheduler.get_job(job_id)
    if not job:
        return {"error": f"任务 {job_id} 不存在"}

    # 在新线程中立即执行
    from backend.scheduler import jobs
    job_func_map = {
        "collect_a_indices": jobs.job_collect_a_indices,
        "collect_sectors": jobs.job_collect_sectors,
        "collect_concepts": jobs.job_collect_concepts,
        "collect_fund_estimate": jobs.job_collect_fund_estimate,
        "collect_fund_nav": jobs.job_collect_fund_nav,
        "collect_global_index": jobs.job_collect_global_index,
        "collect_news": jobs.job_collect_news,
        "calculate_pnl": jobs.job_calculate_pnl,
        "snapshot_portfolio_daily": jobs.job_snapshot_portfolio_daily,
        "ai_advice": jobs.job_ai_advice,
        "advice_review": jobs.job_advice_review,
        "sync_fund_managers": jobs.job_sync_fund_managers,
        "sync_fund_top_holdings": jobs.job_sync_fund_top_holdings,
        "check_investment_plans": jobs.job_check_investment_plans,
        "daily_fee_accrual": jobs.job_daily_fee_accrual,
        "monthly_decision_review": jobs.job_monthly_decision_review,
    }

    func = job_func_map.get(job_id)
    if func:
        try:
            import inspect
            sig = inspect.signature(func)

            def _run_with_force():
                try:
                    if 'force' in sig.parameters:
                        func(force=True)
                    else:
                        func()
                except Exception as e:
                    logger.error(f"手动触发任务 {job_id} 失败: {e}")

            # 长任务（AI建议/复盘）走专用线程池
            if job_id in ("ai_advice", "advice_review", "sync_fund_managers", "sync_fund_top_holdings", "monthly_decision_review"):
                _long_task_executor.submit(_run_with_force)
                return {"message": f"任务 {job_id} 已提交到长任务线程池执行"}
            else:
                _run_with_force()
                return {"message": f"任务 {job_id} 已手动触发执行完成"}
        except Exception as e:
            return {"error": f"任务执行失败: {str(e)}"}
    else:
        return {"error": f"未找到任务函数: {job_id}"}
