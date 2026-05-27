"""
用户决策复盘服务 — P2.2

核心能力：
1. 从 trades 表自动生成决策快照（30 天后回填结果）
2. 计算"行为偏差雷达图"：追涨/杀跌/频繁交易/跟随建议/自主操作胜率
3. 月度报告：N 次操作、X 次跟 AI（Y 胜）、Z 次反着做、最让你后悔的决策
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from loguru import logger
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.models.ai_advice import AiAdvice
from backend.models.holding import Holding
from backend.models.market_snapshot import MarketSnapshot
from backend.models.trade import Trade
from backend.models.user_decision_review import BehaviorBiasSnapshot, UserDecisionReview


REVIEW_HORIZON_DAYS = 30


def _classify_market_state(change_pct: float) -> str:
    if change_pct > 1.0:
        return "bullish"
    if change_pct < -1.0:
        return "bearish"
    return "neutral"


def _market_state_on(db: Session, target_day: date) -> str:
    """以沪深300 当日涨跌幅近似市场状态"""
    snap = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == "000300.SH",
            MarketSnapshot.snapshot_type == "index",
            MarketSnapshot.snapshot_date <= target_day,
        )
        .order_by(MarketSnapshot.snapshot_date.desc(), MarketSnapshot.snapshot_time.desc())
        .first()
    )
    if not snap:
        return "neutral"
    return _classify_market_state(float(snap.change_pct or 0))


def _classify_user_action(db: Session, trade: Trade) -> tuple[str | None, int | None]:
    """根据 trade 当日是否有 AI 建议，判断 user_action 取值"""
    advice = (
        db.query(AiAdvice)
        .filter(AiAdvice.advice_date == trade.trade_date)
        .order_by(AiAdvice.advice_time.desc())
        .first()
    )
    if not advice:
        return "self", None

    return _classify_user_action_with_advice(trade, advice)


def _classify_user_action_with_advice(trade: Trade, advice: AiAdvice | None) -> tuple[str | None, int | None]:
    """根据已加载的当日 AI 建议判断用户行为，供批量复盘复用。"""
    if not advice:
        return "self", None

    actions = advice.actions or []
    matched = next((a for a in actions if a.get("fund_code") == trade.fund_code), None)
    advice_action = (matched or {}).get("action", "")

    if trade.trade_type == "买入" and advice_action == "add":
        return "follow", advice.id
    if trade.trade_type == "卖出" and advice_action == "reduce":
        return "follow", advice.id
    if (trade.trade_type == "买入" and advice_action == "reduce") or \
       (trade.trade_type == "卖出" and advice_action == "add"):
        return "reverse", advice.id
    return "self", advice.id


def materialize_decisions_from_trades(db: Session, since_days: int = 90) -> int:
    """从 trades 表自动生成 user_decision_reviews 快照（幂等）"""
    cutoff = date.today() - timedelta(days=since_days)
    trades = (
        db.query(Trade)
        .filter(Trade.trade_date >= cutoff)
        .all()
    )
    if not trades:
        return 0

    trade_dates = {t.trade_date for t in trades}
    advice_by_date: dict[date, AiAdvice] = {}
    if trade_dates:
        advice_rows = (
            db.query(AiAdvice)
            .filter(AiAdvice.advice_date.in_(trade_dates))
            .order_by(AiAdvice.advice_date.asc(), AiAdvice.advice_time.desc())
            .all()
        )
        for advice in advice_rows:
            advice_by_date.setdefault(advice.advice_date, advice)

    active_holdings = db.query(Holding).filter(Holding.is_active == True).all()
    total_value_then = sum(float(h.current_value or 0) for h in active_holdings)

    # 已存在快照的 (trade_date, fund_code, decision_type) 集合
    existing_keys = set()
    for r in db.query(UserDecisionReview).filter(UserDecisionReview.decision_date >= cutoff).all():
        existing_keys.add((r.decision_date, r.fund_code, r.decision_type))

    inserted = 0
    for t in trades:
        decision_type = "buy" if t.trade_type == "买入" else "sell"
        key = (t.trade_date, t.fund_code, decision_type)
        if key in existing_keys:
            continue
        user_action, advice_id = _classify_user_action_with_advice(t, advice_by_date.get(t.trade_date))

        db.add(UserDecisionReview(
            advice_id=advice_id,
            fund_code=t.fund_code,
            decision_date=t.trade_date,
            user_action=user_action,
            decision_type=decision_type,
            decision_amount=float(t.amount or 0),
            market_state_then=_market_state_on(db, t.trade_date),
            portfolio_value_then=round(total_value_then, 2),
            fund_nav_then=float(t.nav_price or 0),
        ))
        inserted += 1

    if inserted:
        db.commit()
        logger.info(f"决策快照生成: 新增 {inserted} 条")
    return inserted


def review_pending_decisions(db: Session) -> int:
    """回填 30 天后到期的决策结果"""
    cutoff_decision_day = date.today() - timedelta(days=REVIEW_HORIZON_DAYS)
    pending = (
        db.query(UserDecisionReview)
        .filter(
            UserDecisionReview.is_reviewed == 0,
            UserDecisionReview.decision_date <= cutoff_decision_day,
        )
        .all()
    )
    if not pending:
        return 0

    reviewed = 0
    for r in pending:
        nav_then = float(r.fund_nav_then or 0)
        nav_30d = _fund_nav_on(db, r.fund_code, r.decision_date + timedelta(days=REVIEW_HORIZON_DAYS))
        if not nav_30d or not nav_then:
            continue

        change_pct = (nav_30d - nav_then) / nav_then * 100
        # 判定 outcome：买入后涨为 win，卖出后跌为 win
        if r.decision_type == "buy":
            r.outcome = "win" if change_pct > 1 else ("loss" if change_pct < -1 else "neutral")
        elif r.decision_type == "sell":
            r.outcome = "win" if change_pct < -1 else ("loss" if change_pct > 1 else "neutral")
        else:
            r.outcome = "neutral"

        r.fund_nav_30d = round(nav_30d, 4)
        r.outcome_pct = round(change_pct, 2)
        r.market_state_30d = _market_state_on(db, r.decision_date + timedelta(days=REVIEW_HORIZON_DAYS))
        r.is_reviewed = 1
        r.reviewed_at = datetime.now()
        r.lesson = _generate_lesson(r, change_pct)
        reviewed += 1

    db.commit()
    if reviewed:
        logger.info(f"决策回填: 完成 {reviewed} 条")
    return reviewed


def _fund_nav_on(db: Session, fund_code: str, target_day: date) -> float | None:
    """查找指定日期附近的基金净值（±3 天容差）"""
    snap = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.snapshot_type == "fund",
            MarketSnapshot.symbol == f"fund_{fund_code}",
            MarketSnapshot.snapshot_date >= target_day - timedelta(days=3),
            MarketSnapshot.snapshot_date <= target_day + timedelta(days=3),
        )
        .order_by(MarketSnapshot.snapshot_date.desc())
        .first()
    )
    return float(snap.price) if snap and snap.price else None


def _generate_lesson(r: UserDecisionReview, change_pct: float) -> str:
    if r.outcome == "win":
        if r.user_action == "follow":
            return f"跟随 AI 建议成功：30 天后净值变化 {change_pct:+.2f}%"
        if r.user_action == "reverse":
            return f"反着 AI 建议反而对了：30 天后净值变化 {change_pct:+.2f}%（小心幸存者偏差）"
        return f"主动操作成功：30 天后净值变化 {change_pct:+.2f}%"
    if r.outcome == "loss":
        if r.user_action == "reverse":
            return f"反着 AI 建议被打脸：30 天后净值变化 {change_pct:+.2f}%"
        if r.user_action == "self":
            return f"主动操作失误：30 天后净值变化 {change_pct:+.2f}%"
        return f"跟随 AI 建议失败：30 天后净值变化 {change_pct:+.2f}%（看下当时的市场状态）"
    return f"30 天净值变化平稳：{change_pct:+.2f}%"


# ──────────────── 行为偏差雷达图 ────────────────

def compute_behavior_bias(db: Session, month: str | None = None) -> dict:
    """按月计算行为偏差快照"""
    today = date.today()
    month = month or f"{today.year}-{today.month:02d}"
    start = date(int(month[:4]), int(month[5:7]), 1)
    next_month = (start.month % 12) + 1
    next_year = start.year + (1 if start.month == 12 else 0)
    end = date(next_year, next_month, 1) - timedelta(days=1)

    decisions = (
        db.query(UserDecisionReview)
        .filter(
            UserDecisionReview.decision_date >= start,
            UserDecisionReview.decision_date <= end,
        )
        .all()
    )
    if not decisions:
        return {"month": month, "no_data": True}

    buys = [d for d in decisions if d.decision_type == "buy"]
    sells = [d for d in decisions if d.decision_type == "sell"]
    total = len(decisions)

    # 追涨：买入时市场 bullish 比例
    chase_high = (
        sum(1 for d in buys if d.market_state_then == "bullish") / max(len(buys), 1) * 100
        if buys else 0
    )
    # 杀跌：卖出时市场 bearish 比例
    cut_low = (
        sum(1 for d in sells if d.market_state_then == "bearish") / max(len(sells), 1) * 100
        if sells else 0
    )
    # 频繁交易：本月交易次数 / 持仓数
    holdings_count = db.query(Holding).filter(Holding.is_active == True).count() or 1
    frequent = min(100, total / holdings_count * 25)

    follow_decisions = [d for d in decisions if d.user_action == "follow"]
    reverse_decisions = [d for d in decisions if d.user_action == "reverse"]
    self_decisions = [d for d in decisions if d.user_action == "self"]
    follow_advice_rate = len(follow_decisions) / total * 100 if total else 0

    reviewed = [d for d in decisions if d.is_reviewed]
    follow_reviewed = [d for d in follow_decisions if d.is_reviewed]
    reverse_reviewed = [d for d in reverse_decisions if d.is_reviewed]
    self_reviewed = [d for d in self_decisions if d.is_reviewed]

    def _win_rate(items):
        if not items: return 0
        return sum(1 for d in items if d.outcome == "win") / len(items) * 100

    follow_win = _win_rate(follow_reviewed)
    reverse_win = _win_rate(reverse_reviewed)
    self_win = _win_rate(self_reviewed)

    # 最让你后悔的决策：reviewed=1 且 outcome=loss 中 outcome_pct 最负的
    losses = [d for d in reviewed if d.outcome == "loss"]
    biggest_regret = ""
    if losses:
        worst = min(losses, key=lambda d: float(d.outcome_pct or 0))
        biggest_regret = (
            f"{worst.decision_date} {worst.decision_type} {worst.fund_code} "
            f"¥{float(worst.decision_amount or 0):,.0f}，30 天后净值 {float(worst.outcome_pct or 0):+.2f}%"
        )

    # 平均持有天数：buy→sell 的间隔（粗算：本月所有 sell 的持仓 created_at 距 sell 日期）
    avg_holding_days = 0.0
    if sells:
        fund_codes = {s.fund_code for s in sells if s.fund_code}
        holding_created_at = {}
        if fund_codes:
            rows = (
                db.query(Holding.fund_code, Holding.created_at)
                .filter(Holding.fund_code.in_(fund_codes))
                .all()
            )
            holding_created_at = {code: created_at for code, created_at in rows if created_at}
        days_list = []
        for s in sells:
            created_at = holding_created_at.get(s.fund_code)
            if created_at:
                days_list.append((s.decision_date - created_at.date()).days)
        if days_list:
            avg_holding_days = sum(days_list) / len(days_list)

    snapshot = {
        "month": month,
        "chase_high_score": round(chase_high, 2),
        "cut_low_score": round(cut_low, 2),
        "frequent_trade_score": round(frequent, 2),
        "avg_holding_days": round(avg_holding_days, 1),
        "follow_advice_rate": round(follow_advice_rate, 2),
        "follow_win_rate": round(follow_win, 2),
        "reverse_win_rate": round(reverse_win, 2),
        "self_win_rate": round(self_win, 2),
        "biggest_regret": biggest_regret,
        "totals": {
            "total_decisions": total,
            "follow_count": len(follow_decisions),
            "reverse_count": len(reverse_decisions),
            "self_count": len(self_decisions),
            "reviewed_count": len(reviewed),
        },
    }
    return snapshot


def persist_monthly_snapshot(db: Session, month: str | None = None) -> dict:
    """月报 → behavior_bias_snapshots（幂等）"""
    snap = compute_behavior_bias(db, month)
    if snap.get("no_data"):
        return snap

    row = db.query(BehaviorBiasSnapshot).filter(BehaviorBiasSnapshot.month == snap["month"]).first()
    if not row:
        row = BehaviorBiasSnapshot(month=snap["month"])
        db.add(row)
    for k in ("chase_high_score", "cut_low_score", "frequent_trade_score",
              "avg_holding_days", "follow_advice_rate",
              "follow_win_rate", "reverse_win_rate", "self_win_rate"):
        setattr(row, k, snap[k])
    row.biggest_regret = snap["biggest_regret"]
    db.commit()
    return snap


def list_recent_snapshots(db: Session, limit: int = 12) -> list[dict]:
    rows = (
        db.query(BehaviorBiasSnapshot)
        .order_by(BehaviorBiasSnapshot.month.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]


def list_decisions(db: Session, month: str | None = None, limit: int = 100) -> list[dict]:
    q = db.query(UserDecisionReview).order_by(UserDecisionReview.decision_date.desc())
    if month:
        start = date(int(month[:4]), int(month[5:7]), 1)
        next_month = (start.month % 12) + 1
        next_year = start.year + (1 if start.month == 12 else 0)
        end = date(next_year, next_month, 1) - timedelta(days=1)
        q = q.filter(UserDecisionReview.decision_date >= start,
                     UserDecisionReview.decision_date <= end)
    rows = q.limit(limit).all()
    return [r.to_dict() for r in rows]


def run_full_review(db: Session | None = None) -> dict:
    """完整跑一遍：生成快照 → 回填 30 天结果 → 持久化当月雷达图"""
    own = db is None
    from backend.database import SessionLocal
    db = db or SessionLocal()
    try:
        inserted = materialize_decisions_from_trades(db)
        reviewed = review_pending_decisions(db)
        snap = persist_monthly_snapshot(db)
        return {"inserted": inserted, "reviewed": reviewed, "snapshot": snap}
    finally:
        if own:
            db.close()
