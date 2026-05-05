"""
财经新闻采集服务
"""
import traceback
import os
from datetime import datetime
from dateutil import parser as dateutil_parser
from loguru import logger

from backend.database import SessionLocal
from backend.models.news import News
from backend.models.holding import Holding
from backend.models.fund import Fund  # noqa: F401 - ensure SQLAlchemy relationship is registered
from backend.models.trade import Trade  # noqa: F401 - ensure SQLAlchemy relationship is registered


POSITIVE_KEYWORDS = ("利好", "上涨", "增长", "突破", "回暖", "降准", "降息", "增持", "创新高", "超预期")
NEGATIVE_KEYWORDS = ("利空", "下跌", "回落", "风险", "承压", "减持", "亏损", "低于预期", "监管", "违约")


def classify_sentiment(title: str, content: str = "") -> str:
    """轻量新闻情绪标注，供本地AI建议做输入特征。"""
    text = f"{title} {content}"
    positive_score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    negative_score = sum(1 for word in NEGATIVE_KEYWORDS if word in text)
    if positive_score > negative_score:
        return "positive"
    if negative_score > positive_score:
        return "negative"
    return "neutral"


def collect_news():
    """采集财经新闻"""
    for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
        os.environ.pop(key, None)
    os.environ['NO_PROXY'] = '*'
    os.environ['no_proxy'] = '*'
    db = SessionLocal()
    try:
        import akshare as ak
        logger.info("开始采集财经新闻...")

        count = 0

        # 1. 采集东方财富7x24快讯，优先保证今日新闻
        try:
            df_global = ak.stock_info_global_em()
            if df_global is not None and not df_global.empty:
                for _, row in df_global.head(80).iterrows():
                    title = str(row.get("标题", ""))
                    content = str(row.get("摘要", ""))
                    url = str(row.get("链接", ""))
                    publish_time_raw = row.get("发布时间", "")
                    publish_time = None
                    if publish_time_raw:
                        try:
                            publish_time = dateutil_parser.parse(str(publish_time_raw))
                        except (ValueError, TypeError):
                            publish_time = None
                    if not title:
                        continue
                    existing = db.query(News).filter(News.title == title).first()
                    if existing:
                        continue
                    news = News(
                        title=title,
                        content=content[:500] if content else "",
                        source="东方财富快讯",
                        url=url,
                        keyword="今日快讯",
                        sentiment=classify_sentiment(title, content),
                        publish_time=publish_time,
                    )
                    db.add(news)
                    count += 1
        except Exception as e:
            logger.warning(f"东方财富快讯采集失败: {e}")

        # 2. 采集财联社快讯作为补充
        try:
            df_cls = ak.stock_info_global_cls()
            if df_cls is not None and not df_cls.empty:
                for _, row in df_cls.head(80).iterrows():
                    title = str(row.get("标题", "")) or str(row.get("内容", ""))[:80]
                    content = str(row.get("内容", ""))
                    publish_date = str(row.get("发布日期", ""))
                    publish_time_part = str(row.get("发布时间", ""))
                    publish_time = None
                    if publish_date and publish_time_part:
                        try:
                            publish_time = dateutil_parser.parse(f"{publish_date} {publish_time_part}")
                        except (ValueError, TypeError):
                            publish_time = None
                    if not title:
                        continue
                    existing = db.query(News).filter(News.title == title).first()
                    if existing:
                        continue
                    news = News(
                        title=title,
                        content=content[:500] if content else "",
                        source="财联社",
                        url="",
                        keyword="今日快讯",
                        sentiment=classify_sentiment(title, content),
                        publish_time=publish_time,
                    )
                    db.add(news)
                    count += 1
        except Exception as e:
            logger.warning(f"财联社快讯采集失败: {e}")

        # 3. 采集大盘要闻
        try:
            df_news = ak.stock_news_em(symbol="大盘")
            if df_news is not None and not df_news.empty:
                for _, row in df_news.iterrows():
                    title = str(row.get("新闻标题", ""))
                    content = str(row.get("新闻内容", ""))
                    url = str(row.get("新闻链接", ""))
                    publish_time_raw = row.get("发布时间", "")

                    # 将时间字符串转为 datetime 对象
                    publish_time = None
                    if publish_time_raw:
                        try:
                            if isinstance(publish_time_raw, datetime):
                                publish_time = publish_time_raw
                            else:
                                publish_time = dateutil_parser.parse(str(publish_time_raw))
                        except (ValueError, TypeError):
                            publish_time = None

                    # 去重
                    existing = db.query(News).filter(News.title == title).first()
                    if existing:
                        continue

                    news = News(
                        title=title,
                        content=content[:500] if content else "",  # 只存摘要
                        source="东方财富",
                        url=url,
                        keyword="大盘",
                        sentiment=classify_sentiment(title, content),
                        publish_time=publish_time,
                    )
                    db.add(news)
                    count += 1
        except Exception as e:
            logger.warning(f"大盘新闻采集失败: {e}")

        # 4. 采集持仓基金相关新闻
        holdings = db.query(Holding).filter(Holding.is_active == True).all()
        fund_codes = list(set(h.fund_code for h in holdings))

        for code in fund_codes:
            try:
                df_fund_news = ak.stock_news_em(symbol=code)
                if df_fund_news is None or df_fund_news.empty:
                    continue

                for _, row in df_fund_news.iterrows():
                    title = str(row.get("新闻标题", ""))
                    content = str(row.get("新闻内容", ""))
                    url = str(row.get("新闻链接", ""))
                    publish_time_raw = row.get("发布时间", "")

                    # 将时间字符串转为 datetime 对象
                    publish_time = None
                    if publish_time_raw:
                        try:
                            if isinstance(publish_time_raw, datetime):
                                publish_time = publish_time_raw
                            else:
                                publish_time = dateutil_parser.parse(str(publish_time_raw))
                        except (ValueError, TypeError):
                            publish_time = None

                    existing = db.query(News).filter(News.title == title).first()
                    if existing:
                        continue

                    news = News(
                        title=title,
                        content=content[:500] if content else "",
                        source="东方财富",
                        url=url,
                        keyword=code,
                        sentiment=classify_sentiment(title, content),
                        publish_time=publish_time,
                    )
                    db.add(news)
                    count += 1

            except Exception as e:
                logger.warning(f"基金 {code} 新闻采集失败: {e}")
                continue

        db.commit()
        logger.info(f"新闻采集完成，新增 {count} 条")

    except Exception as e:
        logger.error(f"新闻采集失败: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


if __name__ == "__main__":
    collect_news()
