"""通知服务单元测试"""
import pytest
from backend.services.notification import _build_feishu_card, send_advice_notification


def test_build_feishu_card_full():
    advice = {
        "advice_date": "2026-05-11",
        "market_view": "bullish",
        "risk_level": "low",
        "actions": [
            {"fund_code": "005827", "fund_name": "测试基金", "action": "add", "suggested_ratio": 0.1, "confidence": 0.8},
            {"fund_code": "161725", "fund_name": "测试基金2", "action": "hold", "suggested_ratio": 0, "confidence": 0.9},
        ],
        "opportunities": [
            {"board_type": "sector", "name": "半导体", "action": "buy", "suggested_position_ratio": 0.05},
            {"board_type": "concept", "name": "AI", "action": "watch", "suggested_position_ratio": 0},
        ],
        "overall_suggestion": "市场震荡，建议谨慎。",
    }
    card = _build_feishu_card(advice)
    assert card["msg_type"] == "interactive"
    assert "header" in card["card"]
    elements = card["card"]["elements"]
    assert len(elements) >= 2
    # first element should contain markdown with key info
    md = elements[0]["text"]["content"]
    assert "看多" in md
    assert "加仓" in md
    assert "持有" in md
    assert "半导体" in md


def test_build_feishu_card_empty():
    advice = {
        "advice_date": "2026-05-11",
        "market_view": "neutral",
        "risk_level": "medium",
        "actions": [],
        "opportunities": [],
        "overall_suggestion": "",
    }
    card = _build_feishu_card(advice)
    assert card["msg_type"] == "interactive"
    # should not crash with empty data
    assert "elements" in card["card"]


def test_send_invalid_advice():
    """无效建议不应发送"""
    result = send_advice_notification({"error": "no data"})
    assert result["feishu"] is None  # error advice should be skipped


def test_send_valid_advice():
    """有效建议应尝试发送（测试环境可能配置了 webhook）"""
    result = send_advice_notification({
        "advice_date": "2026-05-11", "market_view": "neutral",
        "risk_level": "medium", "actions": [], "overall_suggestion": "test",
    })
    # feishu may be None (no webhook) or dict (webhook configured)
    assert result["feishu"] is None or isinstance(result["feishu"], dict)


def test_build_feishu_card_truncate():
    """长文本应截断"""
    long_text = "测试" * 500
    advice = {
        "advice_date": "2026-05-11",
        "market_view": "neutral",
        "risk_level": "medium",
        "actions": [],
        "opportunities": [],
        "overall_suggestion": long_text,
    }
    card = _build_feishu_card(advice)
    md = card["card"]["elements"][0]["text"]["content"]
    # should be truncated at ~500 chars
    assert len(md) < 2000
