"""
AI 建议复盘服务
跟踪每条建议的后续实际表现，计算命中率
"""
import json
from datetime import date, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from backend.models.ai_advice import AiAdvice
from backend.models.ai_advice_review import AiAdviceReview
from backend.models.market_snapshot import MarketSnapshot
from backend.models.holding import Holding

# 命中阈值：涨跌幅绝对值 >1% 为有效方向性变化
DIRECTION_THRESHOLD = 1.0  # %


def _get_portfolio_value_at(db: Session, target_date: date) -> float | None:
    """获取组合在指定日期的总市值"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    if not holdings:
        return None

    total = 0.0
    for h in holdings:
        snap = db.query(MarketSnapshot).filter(
            MarketSnapshot.snapshot_type == "fund",
            MarketSnapshot.symbol == f"fund_{h.fund_code}",
            MarketSnapshot.snapshot_date == target_date,
        ).order_by(MarketSnapshot.snapshot_time.desc()).first()

        if snap and snap.price:
            total += float(h.shares or 0) * float(snap.price)
        else:
            total += float(h.current_value or 0)

    return total if total > 0 else None


def _get_market_return(db: Session, from_date: date, to_date: date) -> float | None:
    """获取沪深300在两日之间的收益"""
    start_snap = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == "000300.SH",
        MarketSnapshot.snapshot_type == "index",
        MarketSnapshot.snapshot_date == from_date,
    ).order_by(MarketSnapshot.snapshot_time.desc()).first()

    end_snap = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == "000300.SH",
        MarketSnapshot.snapshot_type == "index",
        MarketSnapshot.snapshot_date == to_date,
    ).order_by(MarketSnapshot.snapshot_time.desc()).first()

    if start_snap and end_snap and start_snap.price and end_snap.price:
        return (float(end_snap.price) - float(start_snap.price)) / float(start_snap.price) * 100
    return None


def _get_portfolio_return(db: Session, from_date: date, to_date: date) -> float | None:
    """获取组合在两日之间的收益率"""
    from_val = _get_portfolio_value_at(db, from_date)
    to_val = _get_portfolio_value_at(db, to_date)
    if from_val and to_val and from_val > 0:
        return (to_val - from_val) / from_val * 100
    return None


def _determine_hit(advice: AiAdvice, actual_return: float) -> tuple[str, str]:
    """
    判定命中结果。
    阈值：涨跌幅绝对值 >1% 为方向性变化
    """
    market_view = (advice.market_view or "neutral").lower()
    structured = {}
    suggested_action = "hold"

    if advice.structured_output:
        try:
            s = json.loads(advice.structured_output)
            sa = s.get("suggested_action", {})
            if isinstance(sa, dict):
                suggested_action = sa.get("action", "hold")
            structured = s
        except (json.JSONDecodeError, TypeError):
            pass

    # 实际涨跌方向
    is_up = actual_return > DIRECTION_THRESHOLD
    is_down = actual_return < -DIRECTION_THRESHOLD
    is_flat = not is_up and not is_down

    direction_label = "上涨" if is_up else ("下跌" if is_down else "震荡")

    if market_view == "bullish" or suggested_action == "add":
        if is_up:
            return "hit", f"看多正确，实际{direction_label} {actual_return:+.2f}%"
        elif is_flat:
            return "partial", f"看多但实际{direction_label} {actual_return:+.2f}%，方向弱于预期"
        else:
            return "miss", f"看多但实际{direction_label} {actual_return:+.2f}%，方向判断错误"

    elif market_view == "bearish" or suggested_action == "reduce":
        if is_down:
            return "hit", f"看空正确，实际{direction_label} {actual_return:+.2f}%"
        elif is_flat:
            return "partial", f"看空但实际{direction_label} {actual_return:+.2f}%，跌幅有限"
        else:
            return "miss", f"看空但实际{direction_label} {actual_return:+.2f}%，方向判断错误"

    else:  # neutral / hold
        if is_flat:
            return "hit", f"中性判断正确，实际{direction_label} {actual_return:+.2f}%"
        else:
            return "partial", f"中性但实际{direction_label} {actual_return:+.2f}%"


def _calc_hit_score(hit_result: str) -> float:
    """将命中结果映射为 0-100 分数"""
    if hit_result == "hit":
        return 100.0
    elif hit_result == "partial":
        return 50.0
    return 0.0


def generate_review(db: Session, advice_id: int) -> AiAdviceReview | None:
    """对单条 AI 建议生成复盘"""
    advice = db.query(AiAdvice).filter(AiAdvice.id == advice_id).first()
    if not advice:
        logger.warning(f"复盘失败：建议 {advice_id} 不存在")
        return None

    # 检查是否已有复盘
    existing = db.query(AiAdviceReview).filter(AiAdviceReview.advice_id == advice_id).first()
    if existing:
        return existing

    advice_date = advice.advice_date
    if not advice_date:
        return None

    # 计算 N 日收益
    next_day = advice_date + timedelta(days=1)
    three_day = advice_date + timedelta(days=3)
    five_day = advice_date + timedelta(days=5)
    today = date.today()

    # 跳过未来日期
    if next_day > today:
        return None  # 不够天数

    next_return = _get_portfolio_return(db, advice_date, next_day)
    three_return = _get_portfolio_return(db, advice_date, three_day) if three_day <= today else None
    five_return = _get_portfolio_return(db, advice_date, five_day) if five_day <= today else None

    next_market = _get_market_return(db, advice_date, next_day)
    three_market = _get_market_return(db, advice_date, three_day) if three_day <= today else None
    five_market = _get_market_return(db, advice_date, five_day) if five_day <= today else None

    # 判定命中（以次日为主要依据）
    actual_return = next_return or 0
    hit_result, review_summary = _determine_hit(advice, actual_return)
    hit_score = _calc_hit_score(hit_result)

    # 偏差原因（miss/partial 时）
    error_reason = ""
    if hit_result in ("miss", "partial"):
        reasons = []
        if next_market is not None and next_return is not None:
            diff = next_return - next_market
            reasons.append(f"超额收益 {diff:+.2f}% (组合{next_return:+.2f}% vs 沪深300{next_market:+.2f}%)")

        sa = {}
        if advice.structured_output:
            try:
                sa = json.loads(advice.structured_output).get("suggested_action", {})
            except Exception:
                pass
        confidence = sa.get("confidence") if isinstance(sa, dict) else None
        if confidence and confidence < 0.6:
            reasons.append(f"AI 置信度偏低 ({confidence:.0%})，建议本身不确定性较高")
        if not reasons:
            reasons.append("市场走势与 AI 判断方向不完全一致")
        error_reason = "；".join(reasons)

    review = AiAdviceReview(
        advice_id=advice_id,
        review_date=today,
        next_day_return=round(next_return, 2) if next_return is not None else 0,
        three_day_return=round(three_return, 2) if three_return is not None else 0,
        five_day_return=round(five_return, 2) if five_return is not None else 0,
        next_day_market_return=round(next_market, 2) if next_market is not None else 0,
        three_day_market_return=round(three_market, 2) if three_market is not None else 0,
        five_day_market_return=round(five_market, 2) if five_market is not None else 0,
        hit_result=hit_result,
        hit_score=hit_score,
        review_summary=review_summary,
        error_reason=error_reason,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    logger.info(f"复盘完成 advice#{advice_id}: {hit_result} score={hit_score:.0f} "
                f"next_return={next_return:+.2f}%")
    return review


def batch_review_pending(db: Session) -> dict:
    """批量复盘所有未复盘的够天数建议"""
    today = date.today()
    advices = db.query(AiAdvice).filter(
        AiAdvice.advice_date <= today - timedelta(days=1),  # 至少过了一天
    ).order_by(AiAdvice.advice_date.asc()).all()

    reviewed = 0
    skipped = 0
    for a in advices:
        existing = db.query(AiAdviceReview).filter(AiAdviceReview.advice_id == a.id).first()
        if existing:
            skipped += 1
            continue
        try:
            generate_review(db, a.id)
            reviewed += 1
        except Exception as e:
            logger.warning(f"复盘 advice#{a.id} 失败: {e}")

    return {"reviewed": reviewed, "skipped": skipped, "total": len(advices)}


def get_hit_rate_stats(db: Session, days: int = 90) -> dict:
    """获取命中率统计"""
    cutoff = date.today() - timedelta(days=days)
    reviews = db.query(AiAdviceReview).join(
        AiAdvice, AiAdviceReview.advice_id == AiAdvice.id
    ).filter(
        AiAdvice.advice_date >= cutoff,
        AiAdviceReview.hit_result != "pending",
    ).all()

    total = len(reviews)
    if total == 0:
        return {"total": 0, "message": "暂无足够复盘数据"}

    hits = sum(1 for r in reviews if r.hit_result == "hit")
    partials = sum(1 for r in reviews if r.hit_result == "partial")
    misses = sum(1 for r in reviews if r.hit_result == "miss")

    # 按市场观点分组
    view_stats = {}
    for r in reviews:
        view = r.advice.market_view or "neutral"
        if view not in view_stats:
            view_stats[view] = {"total": 0, "hit": 0, "partial": 0, "miss": 0}
        view_stats[view]["total"] += 1
        view_stats[view][r.hit_result] += 1

    # 按置信度区间分组
    high_conf = low_conf = 0
    high_hit = low_hit = 0
    for r in reviews:
        conf = 0.5
        if r.advice.structured_output:
            try:
                sa = json.loads(r.advice.structured_output).get("suggested_action", {})
                if isinstance(sa, dict):
                    conf = sa.get("confidence", 0.5)
            except Exception:
                pass
        if conf >= 0.65:
            high_conf += 1
            if r.hit_result == "hit":
                high_hit += 1
        else:
            low_conf += 1
            if r.hit_result == "hit":
                low_hit += 1

    return {
        "total": total,
        "hits": hits,
        "partials": partials,
        "misses": misses,
        "hit_rate": round(hits / total * 100, 1),
        "partial_rate": round(partials / total * 100, 1),
        "miss_rate": round(misses / total * 100, 1),
        "effective_rate": round((hits + partials * 0.5) / total * 100, 1),  # partial 算半命中
        "avg_hit_score": round(sum(r.hit_score for r in reviews) / total, 1),
        "by_market_view": {
            k: {
                **v,
                "hit_rate": round(v["hit"] / v["total"] * 100, 1) if v["total"] > 0 else 0,
            }
            for k, v in view_stats.items()
        },
        "by_confidence": {
            "high_confidence_total": high_conf,
            "high_confidence_hit_rate": round(high_hit / high_conf * 100, 1) if high_conf > 0 else 0,
            "low_confidence_total": low_conf,
            "low_confidence_hit_rate": round(low_hit / low_conf * 100, 1) if low_conf > 0 else 0,
        },
    }


def get_review_list(db: Session, page: int = 1, page_size: int = 20) -> dict:
    """获取复盘列表"""
    offset = (page - 1) * page_size
    total = db.query(AiAdviceReview).count()
    reviews = db.query(AiAdviceReview).join(
        AiAdvice, AiAdviceReview.advice_id == AiAdvice.id
    ).order_by(AiAdviceReview.review_date.desc()).offset(offset).limit(page_size).all()

    items = []
    for r in reviews:
        d = r.to_dict()
        d["advice_date"] = str(r.advice.advice_date) if r.advice else None
        d["market_view"] = r.advice.market_view if r.advice else ""
        d["suggested_action"] = ""
        if r.advice and r.advice.structured_output:
            try:
                sa = json.loads(r.advice.structured_output).get("suggested_action", {})
                if isinstance(sa, dict):
                    d["suggested_action"] = sa.get("action", "")
            except Exception:
                pass
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
