"""
/api/ocr/(status|diff-preview|confirm-snapshot) 端点测试 — P2.3

注意：已有 test_ocr_reconcile.py 覆盖 service 层；这里补端点层。
"""
from datetime import date, datetime, timedelta

from backend.models.fund import Fund
from backend.models.holding import Holding
from backend.models.trade import Trade

from .conftest import TestingSessionLocal, client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


def _seed_fund_and_holding(code: str = "005827", *, shares: float = 1000,
                           value: float = 1200, nav: float = 1.2):
    db = TestingSessionLocal()
    try:
        if not db.query(Fund).filter(Fund.fund_code == code).first():
            db.add(Fund(fund_code=code, fund_name="易方达蓝筹精选",
                       fund_type="混合型", latest_nav=nav))
        db.add(Holding(
            fund_code=code, shares=shares, cost_amount=1000,
            current_nav=nav, current_value=value, is_active=True,
            source="manual",
        ))
        db.commit()
    finally:
        db.close()


# ──────────────── 鉴权 ────────────────

def test_ocr_status_requires_auth():
    resp = client.get("/api/ocr/status")
    assert resp.status_code == 401


# ──────────────── /status ────────────────

def test_status_no_holdings():
    resp = client.get("/api/ocr/status", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_holding_count"] == 0
    assert body["due"] is False


def test_status_with_holdings_never_synced():
    _seed_fund_and_holding()
    resp = client.get("/api/ocr/status", headers=_headers())
    body = resp.json()
    assert body["active_holding_count"] == 1
    assert body["last_sync_at"] is None
    assert body["due"] is True
    assert "尚未通过 OCR" in body["message"]


def test_status_recent_sync_not_due():
    _seed_fund_and_holding()
    # 把 holding.source 改成 ocr 且 updated_at 设为今天 → 表示刚同步过
    db = TestingSessionLocal()
    try:
        h = db.query(Holding).first()
        h.source = "ocr_alipay"
        h.updated_at = datetime.now()
        db.commit()
    finally:
        db.close()
    resp = client.get("/api/ocr/status", headers=_headers())
    body = resp.json()
    assert body["due"] is False
    assert body["days_since_last_sync"] == 0


# ──────────────── /diff-preview ────────────────

def test_diff_preview_new_holding():
    """OCR 里有，DB 里没有 → status=new + 可生成买入"""
    db = TestingSessionLocal()
    try:
        # 只种 Fund，不种 Holding，让 nav 来自 fund.latest_nav
        db.add(Fund(fund_code="005827", fund_name="易方达蓝筹精选",
                   fund_type="混合型", latest_nav=1.2))
        db.commit()
    finally:
        db.close()

    payload = {
        "items": [{
            "fund_code": "005827",
            "fund_name": "易方达蓝筹精选",
            "shares": 1000,
            "amount": 1200,
            "source": "alipay",
        }],
        "trade_date": str(date.today()),
    }
    resp = client.post("/api/ocr/diff-preview", headers=_headers(), json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["snapshot_count"] == 1
    assert len(body["diffs"]) == 1
    diff = body["diffs"][0]
    assert diff["status"] == "new"
    assert diff["trade_type"] == "买入"
    assert diff["inferred_shares"] == 1000.0
    assert diff["can_create_trade"] is True


def test_diff_preview_increased_holding():
    """既有 800 份 → OCR 1000 份 → status=increased + 推断 +200"""
    _seed_fund_and_holding(shares=800, value=960)
    payload = {
        "items": [{
            "fund_code": "005827", "fund_name": "易方达蓝筹精选",
            "shares": 1000, "amount": 1200, "source": "alipay",
        }],
        "trade_date": str(date.today()),
    }
    resp = client.post("/api/ocr/diff-preview", headers=_headers(), json=payload)
    body = resp.json()
    diff = body["diffs"][0]
    assert diff["status"] == "increased"
    assert diff["trade_type"] == "买入"
    assert diff["inferred_shares"] == 200.0
    assert diff["share_delta"] == 200.0


def test_diff_preview_missing_holding_appears_in_missing_list():
    """DB 有持仓但 OCR 没有 → missing_holdings 含该基金"""
    _seed_fund_and_holding()
    payload = {"items": [], "trade_date": str(date.today())}
    resp = client.post("/api/ocr/diff-preview", headers=_headers(), json=payload)
    body = resp.json()
    assert len(body["missing_holdings"]) == 1
    assert body["missing_holdings"][0]["fund_code"] == "005827"
    assert "暂不自动按全部赎回" in body["missing_holdings"][0]["warning"]


def test_diff_preview_invalid_item_no_fund_code():
    payload = {
        "items": [{"fund_name": "未知基金", "amount": 1000}],
        "trade_date": str(date.today()),
    }
    resp = client.post("/api/ocr/diff-preview", headers=_headers(), json=payload)
    body = resp.json()
    assert body["summary"]["invalid_item_count"] == 1
    assert "缺少基金代码" in body["invalid_items"][0]["reason"]


def test_diff_preview_duplicate_trade_detection():
    """已存在同日同份额 OCR 交易 → duplicate_trade=true"""
    _seed_fund_and_holding(shares=800, value=960)
    today = date.today()
    db = TestingSessionLocal()
    try:
        db.add(Trade(
            fund_code="005827", trade_type="买入",
            shares=200, nav_price=1.2, amount=240,
            trade_date=today, source="ocr_diff",
        ))
        db.commit()
    finally:
        db.close()

    payload = {
        "items": [{
            "fund_code": "005827", "shares": 1000, "amount": 1200,
            "source": "alipay",
        }],
        "trade_date": str(today),
    }
    resp = client.post("/api/ocr/diff-preview", headers=_headers(), json=payload)
    body = resp.json()
    diff = body["diffs"][0]
    assert diff["duplicate_trade"] is True
    assert diff["can_create_trade"] is False
    assert any("重复" in w for w in diff["warnings"])


# ──────────────── /confirm-snapshot ────────────────

def test_confirm_snapshot_creates_holding_and_trade():
    db = TestingSessionLocal()
    try:
        db.add(Fund(fund_code="005827", fund_name="易方达蓝筹精选",
                   fund_type="混合型", latest_nav=1.2))
        db.commit()
    finally:
        db.close()

    payload = {
        "items": [{
            "fund_code": "005827", "fund_name": "易方达蓝筹精选",
            "shares": 1000, "amount": 1200, "cost_amount": 1100,
            "source": "alipay",
        }],
        "trade_date": str(date.today()),
        "generate_trades": True,
    }
    resp = client.post(
        "/api/ocr/confirm-snapshot",
        headers=_headers(),
        json=payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "trades" in body
    assert body["trades"]["created_count"] == 1
    assert len(body["created"]) == 1

    # DB 应有新增 holding + trade
    db = TestingSessionLocal()
    try:
        assert db.query(Holding).filter(
            Holding.fund_code == "005827", Holding.is_active == True
        ).count() == 1
        assert db.query(Trade).filter(
            Trade.fund_code == "005827", Trade.source == "ocr_diff"
        ).count() == 1
    finally:
        db.close()


def test_confirm_snapshot_skip_trade_generation():
    db = TestingSessionLocal()
    try:
        db.add(Fund(fund_code="005827", fund_name="易方达蓝筹精选",
                   fund_type="混合型", latest_nav=1.2))
        db.commit()
    finally:
        db.close()
    payload = {
        "items": [{"fund_code": "005827", "shares": 1000, "amount": 1200,
                   "source": "alipay"}],
        "trade_date": str(date.today()),
        "generate_trades": False,
    }
    resp = client.post(
        "/api/ocr/confirm-snapshot",
        headers=_headers(),
        json=payload,
    )
    body = resp.json()
    assert body["trades"]["created_count"] == 0
    # 持仓仍写入
    assert len(body["created"]) == 1


def test_diff_preview_validation_rejects_bad_payload():
    """缺 items 字段 → 422"""
    resp = client.post(
        "/api/ocr/diff-preview",
        headers=_headers(),
        json={"trade_date": str(date.today())},
    )
    assert resp.status_code == 422
