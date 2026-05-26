"""
新闻影响持仓分析服务
匹配新闻关键词 → 板块/主题 → 用户持仓基金
"""
from sqlalchemy.orm import Session, joinedload
from loguru import logger
from backend.models.news import News
from backend.models.holding import Holding
from backend.models.fund_tag import FundTag


def _build_fund_tag_index(db: Session) -> dict[str, list[dict]]:
    """构建 {关键词: [基金信息]} 索引"""
    tags = db.query(FundTag).all()
    holdings = db.query(Holding).options(joinedload(Holding.fund)).filter(Holding.is_active == True).all()
    fund_info = {h.fund_code: h.fund for h in holdings}

    index: dict[str, list[dict]] = {}
    for t in tags:
        name = t.tag_name.lower()
        if name not in index:
            index[name] = []
        info = fund_info.get(t.fund_code)
        index[name].append({
            "fund_code": t.fund_code,
            "fund_name": info.fund_name if info else "",
            "tag_type": t.tag_type,
        })
    return index


def get_news_impact(db: Session, news_id: int) -> dict:
    """获取单条新闻对持仓的影响"""
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        return {"error": "新闻不存在"}

    title = (news.title or "").lower()
    content = (news.content or "").lower()
    text = title + " " + content
    sentiment = news.sentiment or "neutral"

    index = _build_fund_tag_index(db)
    affected = []
    seen_codes = set()

    for keyword, funds in index.items():
        if keyword in text and len(keyword) >= 2:
            for f in funds:
                if f["fund_code"] not in seen_codes:
                    seen_codes.add(f["fund_code"])
                    # 影响方向
                    if sentiment == "positive":
                        direction = "利好"
                    elif sentiment == "negative":
                        direction = "利空"
                    else:
                        direction = "中性"
                    affected.append({
                        "fund_code": f["fund_code"],
                        "fund_name": f["fund_name"],
                        "direction": direction,
                        "matched_keyword": keyword,
                    })

    impact_level = "高" if len(affected) >= 3 else ("中" if len(affected) >= 1 else "低")

    return {
        "news_id": news_id,
        "title": news.title,
        "sentiment": sentiment,
        "affected_funds": affected,
        "affected_count": len(affected),
        "impact_level": impact_level,
    }


def get_daily_impact_report(db: Session) -> dict:
    """当日新闻持仓影响汇总"""
    from datetime import date, datetime, timedelta

    today = date.today()
    start_at = datetime.combine(today - timedelta(days=1), datetime.min.time())
    news_list = db.query(News).filter(News.publish_time >= start_at).order_by(News.publish_time.desc()).all()

    index = _build_fund_tag_index(db)
    fund_impact: dict[str, dict] = {}

    for news in news_list:
        title = (news.title or "").lower()
        sentiment = news.sentiment or "neutral"
        seen = set()

        for keyword, funds in index.items():
            if keyword in title and len(keyword) >= 2:
                for f in funds:
                    code = f["fund_code"]
                    if code not in seen:
                        seen.add(code)
                        if code not in fund_impact:
                            fund_impact[code] = {
                                "fund_code": code,
                                "fund_name": f["fund_name"],
                                "positive_count": 0,
                                "negative_count": 0,
                                "neutral_count": 0,
                                "latest_impact": "",
                            }
                        fund_impact[code][f"{sentiment}_count"] += 1

    for code, impact in fund_impact.items():
        if impact["positive_count"] > impact["negative_count"]:
            impact["latest_impact"] = "偏正面"
        elif impact["negative_count"] > impact["positive_count"]:
            impact["latest_impact"] = "偏负面"
        else:
            impact["latest_impact"] = "中性"

    sorted_impacts = sorted(fund_impact.values(), key=lambda x: x["positive_count"] + x["negative_count"], reverse=True)

    return {
        "news_count": len(news_list),
        "fund_impacts": sorted_impacts[:15],
    }
