"""
新闻 API — V2

V2 改动：
- BUG 修复：原 v1 的 /impact/{news_id} 在 /impact/daily 之前定义，daily 会被当成 news_id 参数
  导致 /impact/daily 永远进不到 get_daily_impact。改为严格静态路径优先 + Path(..., ge=1) 限定数字
- 抽出公共查询条件
- 顶部统一 HTTPException 导入，避免函数内反复 import
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.models.news import News
from backend.services.news_classifier import classify_news

router = APIRouter(prefix="/api/news", tags=["新闻资讯"])


@router.get("")
def list_news(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    sub_category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sentiment: Optional[str] = None,
    sort: str = Query("time", pattern="^(time|importance)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(News)
    if keyword:
        query = query.filter(
            (News.keyword.contains(keyword))
            | (News.title.contains(keyword))
            | (News.content.contains(keyword))
            | (News.related_topics.contains(keyword))
        )
    if category and category != "全部":
        query = query.filter(News.category == category)
    if sub_category and sub_category != "全部":
        query = query.filter(News.sub_category == sub_category)
    if start_date:
        query = query.filter(News.publish_time >= start_date)
    if end_date:
        query = query.filter(News.publish_time <= end_date)
    if sentiment:
        query = query.filter(News.sentiment == sentiment)

    total = query.count()
    if sort == "importance":
        query = query.order_by(News.importance_score.desc(), News.publish_time.desc())
    else:
        query = query.order_by(News.publish_time.desc(), News.importance_score.desc())

    offset = (page - 1) * page_size
    news_list = query.offset(offset).limit(page_size).all()

    return {
        "items": [n.to_dict() for n in news_list],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get("/insights/summary")
def news_insights(db: Session = Depends(get_db)):
    from sqlalchemy import func

    recent = db.query(News).order_by(News.publish_time.desc(), News.id.desc()).limit(200).all()
    categories = [
        {"name": name or "推荐", "count": count}
        for name, count in db.query(News.category, func.count(News.id)).group_by(News.category).all()
    ]
    sentiment = {
        name or "neutral": count
        for name, count in db.query(News.sentiment, func.count(News.id)).group_by(News.sentiment).all()
    }

    positive_targets: dict[str, float] = {}
    negative_targets: dict[str, float] = {}
    for item in recent:
        for impact in item.to_dict().get("impact_items", []):
            target = impact.get("target_name")
            if not target:
                continue
            strength = float(impact.get("strength") or 0.5)
            if impact.get("direction") == "利好":
                positive_targets[target] = positive_targets.get(target, 0) + strength
            elif impact.get("direction") == "利空":
                negative_targets[target] = negative_targets.get(target, 0) + strength

    def top_targets(data: dict[str, float]):
        return [
            {"target": key, "score": round(value, 2)}
            for key, value in sorted(data.items(), key=lambda pair: pair[1], reverse=True)[:10]
        ]

    return {
        "categories": categories,
        "sentiment": sentiment,
        "positive_targets": top_targets(positive_targets),
        "negative_targets": top_targets(negative_targets),
        "latest": recent[0].to_dict() if recent else None,
    }


@router.post("/classify-existing")
def classify_existing_news(db: Session = Depends(get_db)):
    import json

    count = 0
    for news in db.query(News).all():
        classified = classify_news(news.title, news.content, news.source, news.keyword)
        news.category = classified.get("category", "推荐")
        news.sub_category = classified.get("sub_category", "全部")
        news.importance_score = classified.get("importance_score", 50)
        news.sentiment = classified.get("sentiment", news.sentiment)
        news.impact_items = json.dumps(classified.get("impact_items", []), ensure_ascii=False)
        news.related_topics = json.dumps(classified.get("related_topics", []), ensure_ascii=False)
        news.is_breaking = bool(classified.get("is_breaking"))
        count += 1
    db.commit()
    return {"message": f"已分类 {count} 条新闻"}


@router.post("/refresh")
def refresh_news():
    from backend.services.news_collector import collect_news

    collect_news()
    return {"message": "新闻刷新已完成"}


# ─── 影响接口：静态路径必须排在动态路径之前 ──────────────────────────────────
@router.get("/impact/daily")
def get_daily_impact(db: Session = Depends(get_db)):
    """当日新闻持仓影响汇总"""
    from backend.services.news_impact_service import get_daily_impact_report

    return get_daily_impact_report(db)


@router.get("/impact/{news_id}")
def get_news_impact(news_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """单条新闻对持仓的影响"""
    from backend.services.news_impact_service import get_news_impact as _impact

    return _impact(db, news_id)


@router.get("/{news_id}")
def get_news(news_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    return news.to_dict()
