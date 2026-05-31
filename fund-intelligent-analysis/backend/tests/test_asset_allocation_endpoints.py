"""
/api/asset-allocation 端点测试 — P1.2

覆盖：targets CRUD、current 计算、deviations + persist、alerts + ack。
"""
from datetime import date

from backend.models.asset_allocation import AssetAllocationTarget, RebalanceAlert
from backend.models.fund import Fund
from backend.models.holding import Holding

from .conftest import TestingSessionLocal, client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


def _seed_holdings():
    """种 2 只基金 + 持仓：1 只 A 股 50000 / 1 只债基 50000，合计 100000"""
    db = TestingSessionLocal()
    try:
        db.add(Fund(fund_code="005827", fund_name="易方达蓝筹精选", fund_type="混合型"))
        db.add(Fund(fund_code="100018", fund_name="富国天利债券", fund_type="债券型"))
        db.add(Holding(
            fund_code="005827", shares=10000, cost_amount=40000,
            current_nav=5, current_value=50000, is_active=True,
        ))
        db.add(Holding(
            fund_code="100018", shares=10000, cost_amount=45000,
            current_nav=5, current_value=50000, is_active=True,
        ))
        db.commit()
    finally:
        db.close()


# ──────────────── 鉴权 ────────────────

def test_targets_requires_auth():
    resp = client.get("/api/asset-allocation/targets")
    assert resp.status_code == 401


# ──────────────── targets PUT 校验 ────────────────

def test_put_targets_rejects_bad_total():
    """总和偏离 100% 超过 1pp → 400"""
    resp = client.put(
        "/api/asset-allocation/targets",
        headers=_headers(),
        json=[
            {"asset_class": "equity_a", "target_pct": 60},
            {"asset_class": "bond", "target_pct": 20},
        ],  # 合计 80
    )
    assert resp.status_code == 400
    assert "100" in resp.json()["detail"]


def test_put_targets_ignores_invalid_class():
    resp = client.put(
        "/api/asset-allocation/targets",
        headers=_headers(),
        json=[
            {"asset_class": "equity_a", "target_pct": 60, "tolerance_pct": 5},
            {"asset_class": "bond", "target_pct": 40, "tolerance_pct": 3},
            {"asset_class": "crypto", "target_pct": 0},  # 非法类被忽略
        ],
    )
    assert resp.status_code == 200
    saved_classes = {it["asset_class"] for it in resp.json()["saved"]}
    assert saved_classes == {"equity_a", "bond"}


def test_targets_upsert_then_list():
    headers = _headers()
    client.put(
        "/api/asset-allocation/targets",
        headers=headers,
        json=[
            {"asset_class": "equity_a", "target_pct": 60, "tolerance_pct": 5},
            {"asset_class": "bond", "target_pct": 30},  # 默认 tolerance=5
            {"asset_class": "gold", "target_pct": 10, "notes": "对冲"},
        ],
    )
    resp = client.get("/api/asset-allocation/targets", headers=headers)
    assert resp.status_code == 200
    items = {it["asset_class"]: it for it in resp.json()["items"]}
    assert items["equity_a"]["target_pct"] == 60
    assert items["bond"]["tolerance_pct"] == 5.0
    assert items["gold"]["label"] == "黄金/贵金属"

    # 再次 PUT → upsert（不重复）
    client.put(
        "/api/asset-allocation/targets",
        headers=headers,
        json=[
            {"asset_class": "equity_a", "target_pct": 70},
            {"asset_class": "bond", "target_pct": 30},
        ],
    )
    resp = client.get("/api/asset-allocation/targets", headers=headers)
    items_after = {it["asset_class"]: it for it in resp.json()["items"]}
    assert items_after["equity_a"]["target_pct"] == 70


def test_delete_targets():
    headers = _headers()
    client.put(
        "/api/asset-allocation/targets",
        headers=headers,
        json=[
            {"asset_class": "equity_a", "target_pct": 60},
            {"asset_class": "bond", "target_pct": 40},
        ],
    )
    resp = client.delete("/api/asset-allocation/targets", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2
    # 列表为空
    resp = client.get("/api/asset-allocation/targets", headers=headers)
    assert resp.json()["items"] == []


# ──────────────── current ────────────────

def test_current_allocation_empty():
    resp = client.get("/api/asset-allocation/current", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_value"] == 0
    assert body["by_class_pct"] == {}


def test_current_allocation_with_holdings():
    _seed_holdings()
    resp = client.get("/api/asset-allocation/current", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_value"] == 100000
    assert body["by_class_pct"]["equity_a"] == 50.0
    assert body["by_class_pct"]["bond"] == 50.0


# ──────────────── deviations ────────────────

def test_deviations_no_targets():
    _seed_holdings()
    resp = client.get("/api/asset-allocation/deviations", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["targets"] == []
    assert "尚未设置" in body["message"]


def test_deviations_with_targets_and_persist():
    _seed_holdings()
    headers = _headers()
    # 目标 60/40，当前 50/50 → equity_a 偏离 -10（add 10000）；bond 偏离 +10（reduce 10000）
    client.put(
        "/api/asset-allocation/targets",
        headers=headers,
        json=[
            {"asset_class": "equity_a", "target_pct": 60, "tolerance_pct": 5},
            {"asset_class": "bond", "target_pct": 40, "tolerance_pct": 5},
        ],
    )

    # persist=false：不写预警
    resp = client.get("/api/asset-allocation/deviations", headers=headers)
    body = resp.json()
    assert body["needs_rebalance"] is True
    devs = {d["asset_class"]: d for d in body["deviations"]}
    assert devs["equity_a"]["suggested_action"] == "add"
    assert devs["equity_a"]["suggested_amount"] == 10000.0
    assert devs["bond"]["suggested_action"] == "reduce"

    # persist=true：写入预警
    resp = client.get(
        "/api/asset-allocation/deviations?persist=true",
        headers=headers,
    )
    assert resp.status_code == 200

    db = TestingSessionLocal()
    try:
        alerts = db.query(RebalanceAlert).all()
        assert len(alerts) == 2  # equity_a + bond 都超出 5pp 容忍
        # 重复 persist 应清掉旧未确认 → 还是 2
        client.get("/api/asset-allocation/deviations?persist=true", headers=headers)
        alerts2 = db.query(RebalanceAlert).all()
        assert len(alerts2) == 2
    finally:
        db.close()


# ──────────────── alerts + ack ────────────────

def test_list_and_ack_alert():
    db = TestingSessionLocal()
    try:
        alert = RebalanceAlert(
            detect_date=date.today(),
            asset_class="equity_a",
            target_pct=60,
            current_pct=70,
            deviation_pct=10,
            suggested_action="reduce",
            suggested_amount=10000,
            is_acknowledged=False,
        )
        db.add(alert)
        db.commit()
        alert_id = alert.id
    finally:
        db.close()

    headers = _headers()
    resp = client.get("/api/asset-allocation/alerts", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["label"] == "A股权益"

    resp = client.put(
        f"/api/asset-allocation/alerts/{alert_id}/ack",
        headers=headers,
    )
    assert resp.status_code == 200
    # only_unack=true 后列表应为空
    resp = client.get("/api/asset-allocation/alerts", headers=headers)
    assert resp.json()["items"] == []
    # only_unack=false 仍可见
    resp = client.get(
        "/api/asset-allocation/alerts?only_unack=false",
        headers=headers,
    )
    assert len(resp.json()["items"]) == 1


def test_ack_alert_404():
    resp = client.put(
        "/api/asset-allocation/alerts/99999/ack",
        headers=_headers(),
    )
    assert resp.status_code == 404
