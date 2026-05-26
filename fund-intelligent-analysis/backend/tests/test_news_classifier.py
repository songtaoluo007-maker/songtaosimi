"""新闻分类器单元测试"""
from backend.services.news_classifier import (
    classify_news, infer_impact_items, infer_overall_sentiment, _has,
)


class TestHas:
    def test_single_word_match(self):
        assert _has("央行降息0.5个百分点", ("降息",)) is True

    def test_no_match(self):
        assert _has("市场平稳运行", ("暴跌", "大涨")) is False

    def test_partial_match_in_tuple(self):
        assert _has("黄金价格创历史新高", ("黄金", "石油")) is True

    def test_empty_text(self):
        assert _has("", ("降息",)) is False


class TestInferImpactItems:
    def test_gold_positive(self):
        items = infer_impact_items("黄金受避险情绪推动大涨", "美元走弱，地缘冲突加剧", "黄金")
        assert len(items) > 0
        gold = [i for i in items if i["target_name"] == "黄金"]
        assert len(gold) > 0
        assert gold[0]["direction"] in ("利好", "中性")

    def test_semiconductor_negative(self):
        items = infer_impact_items("芯片出口限制加码，半导体板块承压", "禁令升级，订单砍单", "半导体")
        semi = [i for i in items if i["target_name"] == "半导体"]
        assert len(semi) > 0

    def test_ai_topic(self):
        items = infer_impact_items("AI大模型发布，算力需求爆发", "政策支持人工智能发展", "人工智能")
        ai = [i for i in items if i["target_name"] == "人工智能"]
        assert len(ai) > 0

    def test_no_topic_match_returns_keyword_item(self):
        items = infer_impact_items("今日天气晴朗", "", "快讯")
        assert len(items) == 0  # keyword is "快讯", no topic match → empty

    def test_neutral_when_no_direction_words(self):
        items = infer_impact_items("半导体行业动态", "芯片市场观察", "半导体")
        semi = [i for i in items if i["target_name"] == "半导体"]
        assert len(semi) > 0
        assert semi[0]["direction"] == "中性"


class TestInferOverallSentiment:
    def test_positive_only(self):
        items = [
            {"direction": "利好", "target_name": "黄金", "strength": 0.72},
        ]
        assert infer_overall_sentiment(items) == "positive"

    def test_negative_only(self):
        items = [
            {"direction": "利空", "target_name": "半导体", "strength": 0.72},
        ]
        assert infer_overall_sentiment(items) == "negative"

    def test_mixed(self):
        items = [
            {"direction": "利好", "target_name": "黄金", "strength": 0.72},
            {"direction": "利空", "target_name": "半导体", "strength": 0.65},
        ]
        assert infer_overall_sentiment(items) == "mixed"

    def test_neutral_default(self):
        items = [{"direction": "中性", "target_name": "大盘", "strength": 0.35}]
        assert infer_overall_sentiment(items) == "neutral"


class TestClassifyNews:
    def test_headline_keyword_gets_headline_category(self):
        result = classify_news("国务院发布经济刺激政策", "央行跟进降息", "东方财富快讯", "快讯")
        assert result["category"] in ("头条", "7x24")
        assert 0 <= result["importance_score"] <= 100

    def test_fund_code_detects_holding_category(self):
        result = classify_news("基金净值更新", "", "", "110011")
        assert result["category"] == "持仓相关"

    def test_macro_keywords(self):
        result = classify_news("央行发布利率决议", "人民币汇率稳定", "", "宏观")
        assert result["category"] in ("宏观", "国际", "国际", "7x24")
        assert 0 <= result["importance_score"] <= 100

    def test_breaking_news_high_score(self):
        result = classify_news("突发降息50基点", "央行紧急降息", "财联社", "快讯")
        assert result["is_breaking"] is True
        assert result["importance_score"] >= 62  # 7x24 base 50 + 12

    def test_importance_never_exceeds_100(self):
        result = classify_news(
            "重磅突发制裁降息降准涨停跌停",
            "国务院证监会发改委财政部商务部",
            "东方财富快讯",
            "快讯",
        )
        assert result["importance_score"] <= 100

    def test_returns_required_keys(self):
        result = classify_news("测试标题", "测试内容", "测试来源", "测试")
        required = {"category", "sub_category", "importance_score", "sentiment", "impact_items", "related_topics", "is_breaking"}
        assert required.issubset(result.keys())
