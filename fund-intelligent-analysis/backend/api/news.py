from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.database import get_db
from backend.models.news import News

router = APIRouter(prefix="/api/news", tags=["新闻资讯"])


@router.get("")
def list_news(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sentiment: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """新闻列表"""
    query = db.query(News)
    if keyword:
        query = query.filter(
            (News.keyword.contains(keyword)) | (News.title.contains(keyword))
        )
    if start_date:
        query = query.filter(News.publish_time >= start_date)
    if end_date:
        query = query.filter(News.publish_time <= end_date)
    if sentiment:
        query = query.filter(News.sentiment == sentiment)

    news_list = query.order_by(News.publish_time.desc()).limit(limit).all()
    return [n.to_dict() for n in news_list]


@router.post("/refresh")
def refresh_news():
    """立即刷新财经新闻"""
    from backend.services.news_collector import collect_news
    collect_news()
    return {"message": "新闻刷新已完成"}


@router.get("/{news_id}")
def get_news(news_id: int, db: Session = Depends(get_db)):
    """新闻详情"""
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="新闻不存在")
    return news.to_dict()
