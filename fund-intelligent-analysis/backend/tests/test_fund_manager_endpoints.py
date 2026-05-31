"""
基金经理 + 预警 API 端点测试 — P0.2

避免真实 HTTP：monkeypatch `fetch_managers_from_eastmoney`。
"""
from datetime import date, timedelta

import pytest

from backend.models.fund import Fund
from backend.models.fund_manager import FundManager, ManagerAlert
from backend.models.holding import Holding
from backend.services import fund_manager_service_v3 as svc

from .conftest import TestingSessionLocal, client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


def _seed_fund(code: str = "005827"):
    db = TestingSessionLocal()
    try:
        if not db.query(Fund).filter(Fund.fund_code == code).first():
            db.add(Fund(fund_code=code, fund_name="易方达蓝筹精选", fund_type="混合型"))
            db.commit()
    finally:
        db.close()


# ──────────────── 鉴权 ────────────────

def test_fund_managers_requires_auth():
    resp = client.get("/api/funds/005827/managers")
    assert resp.status_code == 401


def test_manager_alerts_requires_auth():
    resp = client.get("/api/manager-alerts")
    assert resp.status_code == 401


# ──────────────── 读取空状态 ────────────────

def test_get_fund_managers_empty():
    resp = client.get("/api/funds/005827/managers", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["fund_code"] == "005827"
    assert body["current"] == []
    assert body["history"] == []


def test_list_alerts_empty():
    resp = client.get("/api/manager-alerts", headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ──────────────── sync 单只（含变更检测） ────────────────

def test_sync_single_detects_departure_and_new_join(monkeypatch):
    """旧经理 = 张坤；新经理 = 萧楠 → 应产生 1 个 departure（high）+ 1 个 new_join（medium）"""
    _seed_fund()
    db = TestingSessionLocal()
    try:
        # 旧状态：张坤现任
        db.add(FundManager(
            fund_code="005827",
            manager_name="张坤",
            start_date=date(2018, 1, 1),
            end_date=None,
            tenure_return_pct=120.5,
            is_current=True,
        ))
        db.commit()
    finally:
        db.close()

    # 新拉取：萧楠现任，没有张坤
    monkeypatch.setattr(svc, "fetch_managers_from_eastmoney", lambda code: [
        {
            "manager_name": "萧楠",
            "start_date": date(2024, 6, 1),
            "end_date": None,
            "tenure_str": "1年300天",
            "tenure_return_pct": 8.4,
        },
    ])

    resp = client.post("/api/funds/005827/managers/sync", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    types = sorted([a["alert_type"] for a in body["alerts"]])
    assert "departure" in types
    assert "new_join" in types

    # 持久化检查：departure → severity=high
    db = TestingSessionLocal()
    try:
        alerts = db.query(ManagerAlert).order_by(ManagerAlert.severity.asc()).all()
        assert any(a.alert_type == "departure" and a.severity == "high" for a in alerts)
        # 旧经理被标 is_current=False
        old_zhang = db.query(FundManager).filter(
            FundManager.manager_name == "张坤"
        ).first()
        assert old_zhang.is_current is False
        # 新经理被写入
        assert db.query(FundManager).filter(
            FundManager.manager_name == "萧楠", FundManager.is_current == True
        ).first() is not None
    finally:
        db.close()


def test_sync_single_warns_when_source_down(monkeypatch):
    """数据源返回空列表时 → 返回 warning 而非 5xx"""
    _seed_fund()
    monkeypatch.setattr(svc, "fetch_managers_from_eastmoney", lambda code: [])
    resp = client.post("/api/funds/005827/managers/sync", headers=_headers())
    assert resp.status_code == 200
    assert resp.json().get("warning")


# ──────────────── sync-all（全量） ────────────────

def test_sync_all_no_holdings():
    resp = client.post("/api/manager-alerts/sync-all", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["checked"] == 0
    assert "无活跃" in body.get("summary", "")


def test_sync_all_with_holdings(monkeypatch):
    _seed_fund("005827")
    _seed_fund_for("110011")
    db = TestingSessionLocal()
    try:
        db.add(Holding(fund_code="005827", shares=100, is_active=True))
        db.add(Holding(fund_code="110011", shares=200, is_active=True))
        db.commit()
    finally:
        db.close()

    calls: list[str] = []

    def fake_fetch(code: str):
        calls.append(code)
        return [{
            "manager_name": f"经理{code}",
            "start_date": date(2020, 1, 1),
            "end_date": None,
            "tenure_str": "5年",
            "tenure_return_pct": 50.0,
        }]

    monkeypatch.setattr(svc, "fetch_managers_from_eastmoney", fake_fetch)

    resp = client.post("/api/manager-alerts/sync-all", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["checked"] == 2
    assert set(calls) == {"005827", "110011"}


def _seed_fund_for(code: str):
    db = TestingSessionLocal()
    try:
        if not db.query(Fund).filter(Fund.fund_code == code).first():
            db.add(Fund(fund_code=code, fund_name=f"基金{code}", fund_type="混合型"))
            db.commit()
    finally:
        db.close()


# ──────────────── alerts 列表 + 标记已读 ────────────────

def test_list_alerts_only_unread_and_severity_order():
    db = TestingSessionLocal()
    try:
        db.add(ManagerAlert(
            fund_code="005827", alert_type="departure",
            alert_date=date.today(), severity="high",
            detail="张坤离任", is_read=False,
        ))
        db.add(ManagerAlert(
            fund_code="005827", alert_type="new_join",
            alert_date=date.today(), severity="medium",
            detail="萧楠新任", is_read=False,
        ))
        db.add(ManagerAlert(
            fund_code="005827", alert_type="tenure_milestone",
            alert_date=date.today() - timedelta(days=1), severity="low",
            detail="任职 3 年", is_read=True,  # 已读
        ))
        db.commit()
    finally:
        db.close()

    # 默认仅未读
    resp = client.get("/api/manager-alerts", headers=_headers())
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["severity"] == "high"  # high < medium 字典序，severity asc 把 high 放前
    assert items[1]["severity"] == "medium"

    # only_unread=false 应包含已读
    resp = client.get("/api/manager-alerts?only_unread=false", headers=_headers())
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 3


def test_mark_alert_read_happy_path():
    db = TestingSessionLocal()
    try:
        alert = ManagerAlert(
            fund_code="005827", alert_type="new_join",
            alert_date=date.today(), severity="medium",
            detail="测试", is_read=False,
        )
        db.add(alert)
        db.commit()
        alert_id = alert.id
    finally:
        db.close()

    resp = client.put(f"/api/manager-alerts/{alert_id}/read", headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["alert_id"] == alert_id

    db = TestingSessionLocal()
    try:
        fresh = db.query(ManagerAlert).filter(ManagerAlert.id == alert_id).first()
        assert fresh.is_read is True
    finally:
        db.close()


def test_mark_alert_read_404():
    resp = client.put("/api/manager-alerts/99999/read", headers=_headers())
    assert resp.status_code == 404


def test_alerts_limit_validation():
    resp = client.get("/api/manager-alerts?limit=0", headers=_headers())
    assert resp.status_code == 422
    resp = client.get("/api/manager-alerts?limit=500", headers=_headers())
    assert resp.status_code == 422
