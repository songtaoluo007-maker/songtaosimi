"""
/api/decision-review 端点测试 — P2.2

注意：已有 test_decision_review.py 覆盖 service 层；这里补端点层。
"""
from datetime import date, time, timedelta

from backend.models.ai_advice import AiAdvice
from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.trade import Trade
from backend.models.user_decision_review import BehaviorBiasSnapshot

from .conftest import TestingSessionLocal, client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


def _seed_one_follow_decision(when: date | None = None):
    """种一个"跟 AI 加仓"的决策：基金+持仓+AI 建议 add+买入交易"""
    when = when or (date.today() - timedelta(days=1))
    db = TestingSessionLocal()
    try:
        db.add(Fund(fund_code="005827", fund_name="易方达蓝筹精选", fund_type="混合型"))
        db.add(Holding(
            fund_code="005827", shares=1000, cost_amount=1000,
            current_nav=1.2, current_value=1200, is_active=True,
        ))
        db.add(AiAdvice(
            advice_date=when,
            advice_time=time(14, 30),
            actions=[{"fund_code": "005827", "action": "add"}],
            market_view="bullish",
        ))
        db.add(Trade(
            fund_code="005827", trade_type="买入",
            shares=100, nav_price=1.1, amount=110,
            trade_date=when,
        ))
        db.commit()
    finally:
        db.close()


# ──────────────── 鉴权 ────────────────

def test_bias_requires_auth():
    resp = client.get("/api/decision-review/bias")
    assert resp.status_code == 401


# ──────────────── bias GET ────────────────

def test_bias_no_data():
    resp = client.get("/api/decision-review/bias", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["no_data"] is True
    assert "month" in body


def test_bias_with_data_via_run():
    # 通过 /run 一键把决策物化进来，再 GET bias
    _seed_one_follow_decision()
    headers = _headers()
    resp = client.post("/api/decision-review/run", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1

    yesterday = date.today() - timedelta(days=1)
    month = yesterday.strftime("%Y-%m")
    resp = client.get(f"/api/decision-review/bias?month={month}", headers=headers)
    assert resp.status_code == 200
    snap = resp.json()
    assert snap["totals"]["total_decisions"] == 1
    assert snap["totals"]["follow_count"] == 1
    assert snap["follow_advice_rate"] == 100.0


# ──────────────── bias 持久化 + history ────────────────

def test_bias_persist_and_history():
    _seed_one_follow_decision()
    headers = _headers()
    client.post("/api/decision-review/run", headers=headers)

    yesterday = date.today() - timedelta(days=1)
    month = yesterday.strftime("%Y-%m")
    resp = client.post(
        f"/api/decision-review/bias/persist?month={month}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["month"] == month

    # 同月再持久化 → 幂等
    client.post(
        f"/api/decision-review/bias/persist?month={month}",
        headers=headers,
    )
    db = TestingSessionLocal()
    try:
        count = db.query(BehaviorBiasSnapshot).filter(
            BehaviorBiasSnapshot.month == month
        ).count()
        assert count == 1
    finally:
        db.close()

    # history
    resp = client.get("/api/decision-review/bias/history?limit=5", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(it["month"] == month for it in items)


def test_history_limit_validation():
    resp = client.get(
        "/api/decision-review/bias/history?limit=0",
        headers=_headers(),
    )
    assert resp.status_code == 422


# ──────────────── decisions 列表 ────────────────

def test_decisions_empty_returns_empty_list():
    resp = client.get("/api/decision-review/decisions", headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_decisions_filter_by_month():
    _seed_one_follow_decision()
    headers = _headers()
    client.post("/api/decision-review/run", headers=headers)

    yesterday = date.today() - timedelta(days=1)
    month = yesterday.strftime("%Y-%m")
    resp = client.get(
        f"/api/decision-review/decisions?month={month}&limit=10",
        headers=headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["fund_code"] == "005827"
    assert items[0]["user_action"] == "follow"
    assert items[0]["decision_type"] == "buy"


def test_decisions_limit_validation():
    resp = client.get(
        "/api/decision-review/decisions?limit=1000",
        headers=_headers(),
    )
    assert resp.status_code == 422


# ──────────────── run（完整流水） ────────────────

def test_run_idempotent():
    _seed_one_follow_decision()
    headers = _headers()
    resp1 = client.post("/api/decision-review/run", headers=headers)
    resp2 = client.post("/api/decision-review/run", headers=headers)
    assert resp1.status_code == 200 and resp2.status_code == 200
    # 第二次 inserted 应为 0
    assert resp2.json()["inserted"] == 0
