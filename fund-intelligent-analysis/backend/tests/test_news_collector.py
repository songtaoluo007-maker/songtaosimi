"""新闻采集服务 — 工具函数单元测试"""
from datetime import datetime
from backend.services.news_collector import (
    _clean_text, _parse_time, classify_sentiment, _unique,
)


class TestCleanText:
    def test_normal_text(self):
        assert _clean_text("  沪深300指数大涨  ") == "沪深300指数大涨"

    def test_limit_length(self):
        result = _clean_text("A" * 100, limit=10)
        assert len(result) == 10

    def test_none_value(self):
        assert _clean_text(None) == ""

    def test_remove_extra_whitespace(self):
        assert _clean_text("  多个  空格  测试  ") == "多个 空格 测试"


class TestParseTime:
    def test_standard_datetime(self):
        result = _parse_time("2026-05-17 14:30:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 17

    def test_datetime_object_passthrough(self):
        dt = datetime(2026, 5, 17, 14, 30)
        result = _parse_time(dt)
        assert result == dt

    def test_empty_string(self):
        assert _parse_time("") is None

    def test_with_date_part(self):
        result = _parse_time("14:30:00", date_part="2026-05-17")
        assert result is not None
        assert result.hour == 14


class TestClassifySentiment:
    def test_positive(self):
        assert classify_sentiment("市场大涨突破新高", "利好政策推动上涨") == "positive"

    def test_negative(self):
        assert classify_sentiment("市场暴跌回撤", "风险承压减持") == "negative"

    def test_neutral_when_mixed(self):
        # "上涨" positive, "下跌" negative → equal score → neutral
        assert classify_sentiment("指数上涨后下跌", "市场波动") == "neutral"

    def test_neutral_default(self):
        assert classify_sentiment("今日市场平稳", "") == "neutral"


class TestUnique:
    def test_deduplicate(self):
        assert _unique(["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_preserve_order(self):
        assert _unique(["c", "a", "b", "a"]) == ["c", "a", "b"]

    def test_empty(self):
        assert _unique([]) == []
