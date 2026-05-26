"""
News classification and market-impact tagging.

The rules are deliberately transparent. They give the UI and AI advisor a
stable first-pass interpretation before any future LLM-based classification.
"""
from __future__ import annotations

from typing import Any


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


TOPIC_RULES = [
    {
        "target": "黄金",
        "keywords": ("黄金", "金价", "贵金属", "美债", "美元", "避险", "地缘", "通胀"),
        "positive": ("避险", "降息", "美债收益率下行", "美元走弱", "地缘冲突", "通胀"),
        "negative": ("美元走强", "美债收益率上行", "加息", "风险偏好回升"),
    },
    {
        "target": "半导体",
        "keywords": ("半导体", "芯片", "先进封装", "算力", "AI芯片", "国产替代", "光刻", "存储"),
        "positive": ("国产替代", "政策支持", "扩产", "订单", "涨价", "突破", "制裁"),
        "negative": ("出口限制", "禁令", "砍单", "库存", "价格下跌"),
    },
    {
        "target": "人工智能",
        "keywords": ("人工智能", "AI", "大模型", "算力", "数据中心", "机器人", "智能体"),
        "positive": ("订单", "发布", "政策", "增长", "突破", "应用落地"),
        "negative": ("监管", "泡沫", "亏损", "降价", "安全风险"),
    },
    {
        "target": "军工",
        "keywords": ("军工", "航天", "航空", "卫星", "低空经济", "无人机", "国防"),
        "positive": ("订单", "预算", "地缘", "演习", "交付", "政策"),
        "negative": ("降价", "延期", "调查", "预算削减"),
    },
    {
        "target": "医药",
        "keywords": ("医药", "创新药", "医保", "药品", "医疗器械", "CXO", "疫苗"),
        "positive": ("获批", "放量", "出海", "突破", "临床", "政策支持"),
        "negative": ("集采", "降价", "医保谈判", "监管", "失败", "不及预期"),
    },
    {
        "target": "新能源",
        "keywords": ("新能源", "光伏", "锂电", "储能", "风电", "电池", "汽车"),
        "positive": ("需求增长", "装机", "政策", "出口", "涨价", "订单"),
        "negative": ("产能过剩", "价格下跌", "反倾销", "库存", "补贴退坡"),
    },
    {
        "target": "港股",
        "keywords": ("港股", "恒生", "恒指", "南向", "互联网平台", "中概"),
        "positive": ("回购", "南向流入", "降息", "政策", "估值修复"),
        "negative": ("美元走强", "外资流出", "监管", "美债收益率上行"),
    },
    {
        "target": "券商",
        "keywords": ("券商", "证券", "成交额", "资本市场", "并购重组", "IPO"),
        "positive": ("成交额放大", "降准", "降息", "政策支持", "并购重组"),
        "negative": ("成交低迷", "IPO收紧", "监管", "处罚"),
    },
    {
        "target": "银行",
        "keywords": ("银行", "息差", "信贷", "存款", "贷款", "不良"),
        "positive": ("信贷增长", "不良下降", "分红", "估值修复"),
        "negative": ("降息", "息差收窄", "不良上升", "让利"),
    },
    {
        "target": "消费",
        "keywords": ("消费", "白酒", "食品饮料", "旅游", "免税", "零售"),
        "positive": ("促消费", "复苏", "假期", "提价", "增长"),
        "negative": ("需求疲软", "降价", "库存", "不及预期"),
    },
]

MACRO_WORDS = ("央行", "财政", "利率", "降息", "降准", "汇率", "人民币", "CPI", "PPI", "PMI", "社融", "信贷", "宏观")
INTERNATIONAL_WORDS = ("美股", "美联储", "美元", "美债", "欧洲", "日本", "原油", "国际", "海外", "地缘", "关税")
STOCK_WORDS = ("A股", "沪指", "深成指", "创业板", "股市", "涨停", "跌停", "成交额", "板块", "北向", "ETF")
VIEW_WORDS = ("认为", "观点", "预计", "研报", "分析师", "机构", "展望", "建议", "看好", "判断")
FUND_WORDS = ("基金", "ETF", "公募", "私募", "净值", "申购", "赎回")
HEADLINE_WORDS = ("突发", "重磅", "国常会", "国务院", "央行", "证监会", "发改委", "财政部", "商务部")
GOLD_WORDS = ("黄金", "金价", "贵金属", "美元", "美债", "避险")


def classify_news(title: str, content: str = "", source: str = "", keyword: str = "") -> dict[str, Any]:
    text = f"{title} {content} {source} {keyword}"
    is_breaking = source in {"东方财富快讯", "财联社"} or keyword == "快讯"

    if keyword.isdigit() and len(keyword) == 6:
        category = "持仓相关"
    elif _has(text, GOLD_WORDS):
        category = "黄金"
    elif is_breaking:
        category = "7x24"
    elif _has(text, FUND_WORDS):
        category = "基金"
    elif _has(text, INTERNATIONAL_WORDS):
        category = "国际"
    elif _has(text, MACRO_WORDS):
        category = "宏观"
    elif _has(text, STOCK_WORDS):
        category = "股市"
    elif _has(text, HEADLINE_WORDS):
        category = "头条"
    else:
        category = "推荐"

    sub_category = "全部"
    if _has(text, VIEW_WORDS):
        sub_category = "观点"
    elif _has(text, INTERNATIONAL_WORDS):
        sub_category = "国际"
    elif _has(text, MACRO_WORDS):
        sub_category = "宏观"
    elif _has(text, STOCK_WORDS):
        sub_category = "股市"

    importance = 50
    if category in {"头条", "7x24"}:
        importance += 12
    if _has(text, HEADLINE_WORDS):
        importance += 18
    if _has(text, ("涨停", "跌停", "暴跌", "大涨", "大跌", "制裁", "降息", "降准")):
        importance += 10
    if source in {"东方财富快讯", "财联社"}:
        importance += 6
    importance = min(100, importance)

    impacts = infer_impact_items(title, content, keyword)
    sentiment = infer_overall_sentiment(impacts)
    related_topics = sorted({item["target_name"] for item in impacts})

    return {
        "category": category,
        "sub_category": sub_category,
        "importance_score": importance,
        "sentiment": sentiment,
        "impact_items": impacts,
        "related_topics": related_topics,
        "is_breaking": is_breaking,
    }


def infer_overall_sentiment(impact_items: list[dict[str, Any]]) -> str:
    positives = sum(1 for item in impact_items if item.get("direction") == "利好")
    negatives = sum(1 for item in impact_items if item.get("direction") == "利空")
    if positives and negatives:
        return "mixed"
    if positives:
        return "positive"
    if negatives:
        return "negative"
    return "neutral"


def infer_impact_items(title: str, content: str = "", keyword: str = "") -> list[dict[str, Any]]:
    text = f"{title} {content} {keyword}"
    items: list[dict[str, Any]] = []

    for rule in TOPIC_RULES:
        if not _has(text, rule["keywords"]):
            continue
        positive_hit = _has(text, rule["positive"])
        negative_hit = _has(text, rule["negative"])
        if not positive_hit and not negative_hit:
            direction = "中性"
        elif positive_hit and negative_hit:
            direction = "分化"
        else:
            direction = "利好" if positive_hit else "利空"

        strength = 0.55
        if direction in {"利好", "利空"}:
            strength = 0.72
        if _has(text, ("重磅", "突发", "国常会", "央行", "证监会", "制裁", "降息", "降准")):
            strength += 0.12
        if _has(text, ("传闻", "或", "据悉", "可能")):
            strength -= 0.08
        strength = round(max(0.25, min(strength, 0.95)), 2)

        horizon = "短期"
        if _has(text, ("政策", "周期", "产业", "长期", "规划", "改革")):
            horizon = "中长期"
        elif _has(text, ("订单", "业绩", "财报", "库存", "价格")):
            horizon = "中期"

        reason = _impact_reason(rule["target"], direction, text)
        if direction == "分化":
            items.append(_impact_item("利好", rule["target"], strength, horizon, reason, 0.62))
            items.append(_impact_item("利空", rule["target"], round(strength * 0.82, 2), horizon, "同一事件对产业链不同环节存在分化影响。", 0.58))
        elif direction in {"利好", "利空"}:
            items.append(_impact_item(direction, rule["target"], strength, horizon, reason, 0.68))

    if not items and keyword and keyword != "快讯":
        items.append(_impact_item("中性", keyword, 0.35, "短期", "按关键词关联，暂未识别明确利好或利空方向。", 0.35))
    return items[:8]


def _impact_item(direction: str, target: str, strength: float, horizon: str, reason: str, confidence: float) -> dict[str, Any]:
    return {
        "direction": direction,
        "target_type": "板块",
        "target_name": target,
        "strength": strength,
        "horizon": horizon,
        "reason": reason,
        "confidence": confidence,
    }


def _impact_reason(target: str, direction: str, text: str) -> str:
    if target == "黄金":
        return "黄金受美元、美债利率、通胀和避险情绪共同影响。"
    if target == "半导体":
        return "半导体对国产替代、算力需求、政策和供应链变化敏感。"
    if target == "人工智能":
        return "AI主题取决于应用落地、算力投入和政策/监管节奏。"
    if target == "军工":
        return "军工受预算、订单、地缘风险和装备交付预期驱动。"
    if target == "医药":
        return "医药板块受审批、集采、医保和创新药出海影响较大。"
    if target == "新能源":
        return "新能源受需求、价格、出口政策和产能周期影响。"
    if target == "港股":
        return "港股对美元利率、外资风险偏好和平台经济政策敏感。"
    if target == "券商":
        return "券商主要受成交活跃度、资本市场政策和风险偏好影响。"
    if target == "银行":
        return "银行受息差、信贷、不良率和分红预期影响。"
    if target == "消费":
        return "消费板块受居民需求、假期数据、价格和库存周期影响。"
    return f"事件与{target}主题相关，需要结合价格和资金验证。"
