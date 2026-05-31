"""
/api/fund-fees 端点测试 — P2.1
"""
import json
from datetime import date, datetime, timedelta

from backend.models.fund import Fund
from backend.models.fund_fee import FeeDailyAccrual, FundFeeSchedule
from backend.models.holding import Holding

from .conftest import TestingSessionLocal, client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


def _seed_fund(code: str = "005827", name: str = "易方达蓝筹精选"):
    db = TestingSessionLocal()
    try:
        if not db.query(Fund).filter(Fund.fund_code == code).first():
            db.add(Fund(fund_code=code, fund_name=name, fund_type="混合型"))
            db.commit()
    finally:
        db.close()


def _seed_holding(code: str, *, value: float, days_held: int):
    """种持仓，控制 created_at 让赎回费档可被命中"""
    db = TestingSessionLocal()
    try:
        h = Holding(
            fund_code=code,
            shares=value,
            cost_amount=value,
            current_nav=1.0,
            current_value=value,
            is_active=True,
            created_at=datetime.now() - timedelta(days=days_held),
        )
        db.add(h)
        db.commit()
    finally:
        db.close()


# ──────────────── 鉴权 ────────────────

def test_schedules_requires_auth():
    resp = client.get("/api/fund-fees/schedules")
    assert resp.status_code == 401


# ──────────────── schedule CRUD ────────────────

def test_get_schedules_empty():
    resp = client.get("/api/fund-fees/schedules", headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_get_one_404():
    resp = client.get("/api/fund-fees/schedules/999999", headers=_headers())
    assert resp.status_code == 404


def test_upsert_schedule_and_list():
    _seed_fund()
    headers = _headers()
    payload = {
        "purchase_fee_rate": 0.015,
        "purchase_fee_discount": 0.1,
        "management_fee_rate": 0.015,
        "custody_fee_rate": 0.0025,
        "sales_service_fee_rate": 0,
        "redemption_fee_schedule": [
            {"min_days": 0, "max_days": 7, "rate": 0.015},
            {"min_days": 8, "max_days": 365, "rate": 0.005},
            {"min_days": 366, "max_days": 99999, "rate": 0},
        ],
        "source": "manual",
    }
    resp = client.put(
        "/api/fund-fees/schedules/005827",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fund_code"] == "005827"
    assert body["management_fee_rate"] == 0.015
    # redemption_fee_schedule 应被 JSON 序列化后回读为 list
    assert isinstance(body["redemption_fee_schedule"], list)
    assert len(body["redemption_fee_schedule"]) == 3

    # 列表
    resp = client.get("/api/fund-fees/schedules", headers=headers)
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["fund_name"] == "易方达蓝筹精选"

    # 单只
    resp = client.get("/api/fund-fees/schedules/005827", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["purchase_fee_discount"] == 0.1

    # upsert：再 PUT 应更新而不是重复
    resp = client.put(
        "/api/fund-fees/schedules/005827",
        headers=headers,
        json={"management_fee_rate": 0.012},
    )
    assert resp.json()["management_fee_rate"] == 0.012


# ──────────────── 每日计提 ────────────────

def test_accrual_no_holdings():
    resp = client.post("/api/fund-fees/accrual/run", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert "无活跃" in body["message"]


def test_accrual_skips_when_no_schedule():
    _seed_fund()
    _seed_holding("005827", value=100000, days_held=30)
    resp = client.post("/api/fund-fees/accrual/run", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"] == 1
    assert body["inserted"] == 0


def test_accrual_inserts_then_idempotent_updates():
    _seed_fund()
    _seed_holding("005827", value=100000, days_held=30)
    headers = _headers()
    # 配置费率
    client.put(
        "/api/fund-fees/schedules/005827",
        headers=headers,
        json={
            "management_fee_rate": 0.015,
            "custody_fee_rate": 0.0025,
            "sales_service_fee_rate": 0,
            "redemption_fee_schedule": [],
        },
    )

    resp = client.post("/api/fund-fees/accrual/run", headers=headers)
    body = resp.json()
    assert body["inserted"] == 1
    assert body["updated"] == 0
    # 单日 = 100000 * (0.015 + 0.0025) / 365 ≈ 4.79
    daily_total = body["items"][0]["daily_total"]
    assert 4 < daily_total < 5

    # 再跑一次应是 update（幂等）
    resp = client.post("/api/fund-fees/accrual/run", headers=headers)
    body = resp.json()
    assert body["inserted"] == 0
    assert body["updated"] == 1


# ──────────────── 年度账本 ────────────────

def test_yearly_ledger_empty():
    resp = client.get("/api/fund-fees/ledger/yearly", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_fee"] == 0
    assert "尚无" in body["message"]


def test_yearly_ledger_aggregates():
    _seed_fund()
    db = TestingSessionLocal()
    try:
        # 1 月 2 天 + 2 月 1 天计提
        for d in [date(date.today().year, 1, 1), date(date.today().year, 1, 2),
                  date(date.today().year, 2, 1)]:
            db.add(FeeDailyAccrual(
                accrual_date=d, fund_code="005827",
                holding_value=100000,
                daily_mgmt_fee=4.11, daily_custody_fee=0.68, daily_sales_fee=0,
            ))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/fund-fees/ledger/yearly", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == date.today().year
    assert body["total_fee"] > 14  # 3 × ~4.79
    assert len(body["by_fund"]) == 1
    assert len(body["by_month"]) == 2
    assert body["by_fund"][0]["days"] == 3


# ──────────────── 赎回费预估 ────────────────

def test_redemption_estimate_no_holding_404():
    resp = client.get(
        "/api/fund-fees/redemption-estimate/999999",
        headers=_headers(),
    )
    assert resp.status_code == 404


def test_redemption_estimate_hits_first_window_with_warning():
    _seed_fund()
    _seed_holding("005827", value=10000, days_held=3)  # 持有 3 天 → 命中 0-7 档 1.5%
    headers = _headers()
    client.put(
        "/api/fund-fees/schedules/005827",
        headers=headers,
        json={
            "redemption_fee_schedule": [
                {"min_days": 0, "max_days": 7, "rate": 0.015},
                {"min_days": 8, "max_days": 365, "rate": 0.005},
                {"min_days": 366, "max_days": 99999, "rate": 0},
            ],
        },
    )

    resp = client.get(
        "/api/fund-fees/redemption-estimate/005827",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["holding_days"] == 3
    assert body["matched_rate"] == 0.015
    assert body["fee_amount"] == 150.0
    assert body["net_amount"] == 9850.0
    assert body["next_window"]["after_days"] == 5  # 8 - 3
    assert "偏高" in body["warning"]


def test_redemption_estimate_zero_rate_after_long_hold():
    _seed_fund()
    _seed_holding("005827", value=10000, days_held=500)  # 持有 500 天 → 0%
    headers = _headers()
    client.put(
        "/api/fund-fees/schedules/005827",
        headers=headers,
        json={
            "redemption_fee_schedule": [
                {"min_days": 0, "max_days": 7, "rate": 0.015},
                {"min_days": 8, "max_days": 365, "rate": 0.005},
                {"min_days": 366, "max_days": 99999, "rate": 0},
            ],
        },
    )
    resp = client.get(
        "/api/fund-fees/redemption-estimate/005827?redeem_amount=5000",
        headers=headers,
    )
    body = resp.json()
    assert body["matched_rate"] == 0
    assert body["fee_amount"] == 0
    assert body["redeem_amount"] == 5000
    assert "免赎回费" in body["warning"]
