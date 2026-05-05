"""
财经新闻采集服务。

覆盖三类输入：7x24 快讯、市场/政策/行业主题、持仓基金相关资讯。
所有来源统一去重、发布时间解析和轻量情绪标注，供新闻页和 AI 建议使用。
"""
from __future__ import annotations

import os
import traceback
from datetime import datetime
from typing import Iterable

from dateutil import parser as dateutil_parser
from loguru import logger

from backend.database import SessionLocal
from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.news import News
from backend.models.trade import Trade  # noqa: F401 - ensure SQLAlchemy relationship is registered


POSITIVE_KEYWORDS = (
    "利好",
    "上涨",
    "增长",
    "突破",
    "回暖",
    "降准",
    "降息",
    "增持",
    "创新高",
    "超预期",
    "扩张",
    "修复",
    "反弹",
    "改善",
    "加码",
    "回购",
)
NEGATIVE_KEYWORDS = (
    "利空",
    "下跌",
    "回落",
    "风险",
    "承压",
    "减持",
    "亏损",
    "低于预期",
    "监管",
    "违约",
    "收紧",
    "制裁",
    "暴跌",
    "回撤",
    "不及预期",
)

MARKET_TOPIC_KEYWORDS = (
    "大盘",
    "A股",
    "沪深300",
    "政策",
    "央行",
    "财政",
    "利率",
    "汇率",
    "半导体",
    "人工智能",
    "算力",
    "机器人",
    "军工",
    "医药",
    "创新药",
    "新能源",
    "有色金属",
    "黄金",
    "港股",
    "美股",
    "地缘",
    "关税",
)

MAX_GLOBAL_ROWS = 100
MAX_ROWS_PER_TOPIC = 18
MAX_TOPIC_SEARCHES = 30
MAX_HOLDING_FUND_CODES = 16


def _clear_proxy_env() -> None:
    for key in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def _clean_text(value, limit: int | None = None) -> str:
    text = "" if value is None else str(value).strip()
    text = " ".join(text.split())
    return text[:limit] if limit else text


def _parse_time(value, date_part: str = "") -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _clean_text(value)
    if not text:
        return None
    if date_part:
        text = f"{date_part} {text}"
    try:
        return dateutil_parser.parse(text)
    except (ValueError, TypeError, OverflowError):
        return None


def classify_sentiment(title: str, content: str = "") -> str:
    """轻量新闻情绪标注，供本地 AI 建议做输入特征。"""
    text = f"{title} {content}"
    positive_score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    negative_score = sum(1 for word in NEGATIVE_KEYWORDS if word in text)
    if positive_score > negative_score:
        return "positive"
    if negative_score > positive_score:
        return "negative"
    return "neutral"


def _upsert_news(
    db,
    *,
    title: str,
    content: str = "",
    source: str,
    keyword: str,
    url: str = "",
    publish_time: datetime | None = None,
) -> bool:
    title = _clean_text(title, 190)
    content = _clean_text(content, 500)
    url = _clean_text(url, 500)
    if not title:
        return False

    existing = db.query(News).filter(News.title == title).first()
    if existing:
        changed = False
        if existing.keyword == "今日快讯":
            existing.keyword = "快讯"
            changed = True
        if publish_time and not existing.publish_time:
            existing.publish_time = publish_time
            changed = True
        if content and not existing.content:
            existing.content = content
            changed = True
        if url and not existing.url:
            existing.url = url
            changed = True
        if changed:
            existing.sentiment = classify_sentiment(existing.title, existing.content)
        return False

    db.add(
        News(
            title=title,
            content=content,
            source=source,
            url=url,
            keyword=_clean_text(keyword, 50),
            sentiment=classify_sentiment(title, content),
            publish_time=publish_time,
        )
    )
    return True


def _unique(values: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        item = _clean_text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _build_topic_keywords(db) -> list[str]:
    holdings = (
        db.query(Holding)
        .filter(Holding.is_active == True)
        .order_by(Holding.current_value.desc())
        .limit(MAX_HOLDING_FUND_CODES)
        .all()
    )
    fund_codes = [h.fund_code for h in holdings]
    fund_names = [
        row[0]
        for row in db.query(Fund.fund_name).filter(Fund.fund_code.in_(fund_codes)).all()
        if row[0]
    ]
    inferred_topics = []
    for name in fund_names:
        for topic in MARKET_TOPIC_KEYWORDS:
            if topic in name:
                inferred_topics.append(topic)
    return _unique([*MARKET_TOPIC_KEYWORDS, *inferred_topics, *fund_codes])[:MAX_TOPIC_SEARCHES]


def _collect_em_global(db, ak) -> int:
    count = 0
    try:
        df_global = ak.stock_info_global_em()
        if df_global is not None and not df_global.empty:
            for _, row in df_global.head(MAX_GLOBAL_ROWS).iterrows():
                count += int(
                    _upsert_news(
                        db,
                        title=row.get("标题", ""),
                        content=row.get("摘要", ""),
                        source="东方财富快讯",
                        keyword="快讯",
                        url=row.get("链接", ""),
                        publish_time=_parse_time(row.get("发布时间", "")),
                    )
                )
    except Exception as e:
        logger.warning(f"东方财富快讯采集失败: {e}")
    return count


def _collect_cls_global(db, ak) -> int:
    count = 0
    try:
        df_cls = ak.stock_info_global_cls()
        if df_cls is not None and not df_cls.empty:
            for _, row in df_cls.head(MAX_GLOBAL_ROWS).iterrows():
                content = row.get("内容", "")
                count += int(
                    _upsert_news(
                        db,
                        title=row.get("标题", "") or _clean_text(content, 80),
                        content=content,
                        source="财联社",
                        keyword="快讯",
                        publish_time=_parse_time(row.get("发布时间", ""), str(row.get("发布日期", ""))),
                    )
                )
    except Exception as e:
        logger.warning(f"财联社快讯采集失败: {e}")
    return count


def _collect_topic_news(db, ak, keywords: list[str]) -> int:
    count = 0
    for keyword in keywords:
        try:
            df_news = ak.stock_news_em(symbol=keyword)
            if df_news is None or df_news.empty:
                continue
            for _, row in df_news.head(MAX_ROWS_PER_TOPIC).iterrows():
                count += int(
                    _upsert_news(
                        db,
                        title=row.get("新闻标题", ""),
                        content=row.get("新闻内容", ""),
                        source="东方财富",
                        keyword=keyword,
                        url=row.get("新闻链接", ""),
                        publish_time=_parse_time(row.get("发布时间", "")),
                    )
                )
        except Exception as e:
            logger.warning(f"关键词 {keyword} 新闻采集失败: {e}")
            continue
    return count


def collect_news():
    """采集财经新闻。"""
    _clear_proxy_env()
    db = SessionLocal()
    try:
        import akshare as ak

        logger.info("开始采集财经新闻...")
        count = 0
        count += _collect_em_global(db, ak)
        count += _collect_cls_global(db, ak)
        db.commit()

        keywords = _build_topic_keywords(db)
        count += _collect_topic_news(db, ak, keywords)
        db.commit()
        logger.info(f"新闻采集完成，新增 {count} 条，覆盖关键词 {len(keywords)} 个")

    except Exception as e:
        logger.error(f"新闻采集失败: {e}\n{traceback.format_exc()}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    collect_news()
