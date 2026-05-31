"""
/api/toolbox/* 端点测试 — P2.4

注意：已有 test_senior_toolbox.py 覆盖 service 层；这里补端点层。
"""
import json
from datetime import date, datetime, timedelta

from backend.models.fund import Fund
from backend.models.fund_fee import FundFeeSchedule
from backend.models.holding import Holding

from .conftest import TestingSessionLocal, client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


def _seed_fund(code: str, name: str, company: str = "易方达基金"):
    db = TestingSessionLocal()
    try:
        if not db.query(Fund).filter(Fund.fund_code == code).first():
            db.add(Fund(fund_code=code, fund_name=name, fund_type="混合型",
                       company=company, latest_nav=1.5))
            db.commit()
    finally:
        db.close()


def _seed_holding(code: str, *, value: float = 10000, days_held: int = 30):
    db = TestingSessionLocal()
    try:
        db.add(Holding(
            fund_code=code, shares=value, cost_amount=value,
            current_nav=1.0, current_value=value, is_active=True,
            created_at=datetime.now() - timedelta(days=days_held),
        ))
        db.commit()
    finally:
        db.close()


def _seed_fee_schedule(code: str):
    """种典型赎回费档：0-7天 1.5%、8-365天 0.5%、366+天 0%"""
    db = TestingSessionLocal()
    try:
        db.add(FundFeeSchedule(
            fund_code=code,
            management_fee_rate=0.015,
            custody_fee_rate=0.0025,
            sales_service_fee_rate=0,
            redemption_fee_schedule=json.dumps([
                {"min_days": 0, "max_days": 7, "rate": 0.015},
                {"min_days": 8, "max_days": 365, "rate": 0.005},
                {"min_days": 366, "max_days": 99999, "rate": 0},
            ]),
        ))
        db.commit()
    finally:
        db.close()


# ──────────────── 鉴权 ────────────────

def test_milestones_requires_auth():
    resp = client.get("/api/toolbox/milestones")
    assert resp.status_code == 401


# ──────────────── /milestones ────────────────

def test_milestones_empty():
    resp = client.get("/api/toolbox/milestones", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert "暂无持仓" in body["summary"]


def test_milestones_with_holding_imminent_fee_drop():
    """持有 5 天，下一档 8 天 → days_to_fee_drop = 3，应进 imminent"""
    _seed_fund("005827", "易方达蓝筹精选")
    _seed_holding("005827", value=10000, days_held=5)
    _seed_fee_schedule("005827")

    resp = client.get("/api/toolbox/milestones", headers=_headers())
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["fund_code"] == "005827"
    assert item["holding_days"] == 5
    assert item["current_redemption_rate"] == 0.015
    assert item["next_fee_rate"] == 0.005
    assert item["days_to_fee_drop"] == 3
    # 节省 = 10000 × (0.015 - 0.005) = 100
    assert item["savings_at_fee_drop"] == 100.0
    assert len(body["imminent"]) == 1


def test_milestones_run_check_returns_urgent_summary():
    _seed_fund("005827", "易方达蓝筹精选")
    _seed_holding("005827", value=10000, days_held=5)
    _seed_fee_schedule("005827")

    resp = client.post("/api/toolbox/milestones/run-check", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["checked"] == 1
    # 节省金额 100 > 50 → 进 urgent
    assert len(body["urgent"]) == 1


# ──────────────── /quarterly-disclosure ────────────────

def test_quarterly_disclosure_shape():
    resp = client.get("/api/toolbox/quarterly-disclosure", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    # 必有 next_window 或 current_window 之一
    assert "next_window" in body
    assert "last_window" in body
    assert "fund_disclosure_status" in body
    assert isinstance(body["fund_disclosure_status"], list)


# ──────────────── /switch-savings ────────────────

def test_switch_savings_404_when_from_not_held():
    resp = client.get(
        "/api/toolbox/switch-savings?from_code=999999&to_code=005827",
        headers=_headers(),
    )
    # 业务返回 200 + error 字段（非 HTTPException）
    assert resp.status_code == 200
    assert "未持有" in resp.json()["error"]


def test_switch_savings_same_company_recommendation():
    _seed_fund("005827", "易方达蓝筹精选", company="易方达基金")
    _seed_fund("110011", "易方达中小盘", company="易方达基金")
    _seed_holding("005827", value=10000, days_held=5)  # 持有 5 天 → 赎回费 1.5%
    _seed_fee_schedule("005827")
    # 110011 申购费默认 0
    db = TestingSessionLocal()
    try:
        db.add(FundFeeSchedule(
            fund_code="110011",
            purchase_fee_rate=0.015, purchase_fee_discount=0.1,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.get(
        "/api/toolbox/switch-savings?from_code=005827&to_code=110011",
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["same_company"] is True
    # 赎回 1.5% + 申购 0.15% (1.5% × 0.1) ≈ 1.65% × 10000 = 165
    # 转换费 0.5% × 10000 = 50 → 节省 115
    assert body["direct_total_fee"] == 165.0
    assert body["convert_fee"] == 50.0
    assert body["savings"] == 115.0
    assert "建议使用同公司转换" in body["recommendation"]


def test_switch_savings_different_company_warning():
    _seed_fund("005827", "易方达蓝筹精选", company="易方达基金")
    _seed_fund("110011", "汇添富某基金", company="汇添富基金")
    _seed_holding("005827", value=10000, days_held=5)
    _seed_fee_schedule("005827")

    resp = client.get(
        "/api/toolbox/switch-savings?from_code=005827&to_code=110011",
        headers=_headers(),
    )
    body = resp.json()
    assert body["same_company"] is False
    assert "基金公司不同" in body["company_warning"]


def test_switch_savings_convert_fee_validation():
    resp = client.get(
        "/api/toolbox/switch-savings?from_code=a&to_code=b&convert_fee_rate=0.1",
        headers=_headers(),
    )
    assert resp.status_code == 422  # le=0.05


# ──────────────── /holidays ────────────────

def test_holidays_returns_list():
    resp = client.get("/api/toolbox/holidays", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "summary" in body
    assert isinstance(body["items"], list)


# ──────────────── /fee-health ────────────────

def test_fee_health_empty():
    resp = client.get("/api/toolbox/fee-health", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert "暂无持仓" in body["summary"]


def test_fee_health_flags_high_fee_fund():
    _seed_fund("005827", "易方达蓝筹精选")
    _seed_holding("005827", value=100000, days_held=30)
    # 综合 1.5% + 0.5% = 2.0% → high_fee
    db = TestingSessionLocal()
    try:
        db.add(FundFeeSchedule(
            fund_code="005827",
            management_fee_rate=0.015,
            custody_fee_rate=0.005,
            sales_service_fee_rate=0,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/toolbox/fee-health", headers=_headers())
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["is_high_fee"] is True
    # 年化总费 = 100000 × 2% = 2000
    assert item["annual_cost"] == 2000.0
    assert "005827" in body["high_fee_funds"]


def test_fee_health_missing_schedule_listed():
    _seed_fund("005827", "易方达蓝筹精选")
    _seed_holding("005827", value=10000, days_held=30)
    # 故意不种 FundFeeSchedule
    resp = client.get("/api/toolbox/fee-health", headers=_headers())
    body = resp.json()
    assert body["items"] == []
    assert "005827" in body["missing_fee_data"]
