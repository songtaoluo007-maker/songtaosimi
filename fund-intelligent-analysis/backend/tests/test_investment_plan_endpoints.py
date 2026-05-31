"""
/api/investment-plans 端点级测试 — P1.1

覆盖：
- 鉴权拦截（无 token / 错误 token）
- CRUD：create/list/update/delete
- 业务路径：upcoming / smile-curve / reconcile / check-due
- 参数校验：缺字段、plan_type 非法值
"""
from datetime import date, timedelta

from backend.models.fund import Fund
from backend.models.trade import Trade

from .conftest import TestingSessionLocal, client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


def _seed_fund(code: str = "005827", name: str = "易方达蓝筹精选"):
    db = TestingSessionLocal()
    try:
        if not db.query(Fund).filter(Fund.fund_code == code).first():
            db.add(Fund(fund_code=code, fund_name=name, fund_type="混合型", latest_nav=1.5))
            db.commit()
    finally:
        db.close()


# ──────────────── 鉴权 ────────────────

def test_list_plans_requires_auth():
    resp = client.get("/api/investment-plans")
    assert resp.status_code == 401


def test_list_plans_rejects_bad_token():
    resp = client.get(
        "/api/investment-plans",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


# ──────────────── 参数校验 ────────────────

def test_create_plan_missing_field():
    resp = client.post(
        "/api/investment-plans",
        headers=_headers(),
        json={"fund_code": "005827"},  # 缺 plan_type/amount/start_date
    )
    assert resp.status_code == 400
    assert "缺少必填字段" in resp.json()["detail"]


def test_create_plan_invalid_plan_type():
    resp = client.post(
        "/api/investment-plans",
        headers=_headers(),
        json={
            "fund_code": "005827",
            "plan_type": "hourly",  # 非法
            "amount": 1000,
            "start_date": str(date.today()),
        },
    )
    assert resp.status_code == 400
    assert "plan_type" in resp.json()["detail"]


# ──────────────── CRUD happy path ────────────────

def test_create_list_update_delete_plan():
    _seed_fund()
    headers = _headers()

    # 创建月定投，每月 15 号 1000 元
    resp = client.post(
        "/api/investment-plans",
        headers=headers,
        json={
            "fund_code": "005827",
            "plan_name": "蓝筹定投",
            "plan_type": "monthly",
            "amount": 1000,
            "day_of_period": 15,
            "start_date": str(date.today() - timedelta(days=30)),
            "target_amount": 12000,
        },
    )
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["fund_code"] == "005827"
    assert plan["plan_type"] == "monthly"
    plan_id = plan["id"]

    # 列表（带进度统计）
    resp = client.get("/api/investment-plans", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["fund_name"] == "易方达蓝筹精选"
    assert items[0]["target_periods"] == 12  # 12000 / 1000

    # 修改
    resp = client.put(
        f"/api/investment-plans/{plan_id}",
        headers=headers,
        json={"amount": 1500, "notes": "上调金额"},
    )
    assert resp.status_code == 200
    assert resp.json()["amount"] == 1500
    assert resp.json()["notes"] == "上调金额"

    # 停用
    resp = client.delete(f"/api/investment-plans/{plan_id}", headers=headers)
    assert resp.status_code == 200

    # active_only=true（默认）不再返回
    resp = client.get("/api/investment-plans", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []

    # active_only=false 仍可见
    resp = client.get("/api/investment-plans?active_only=false", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_update_plan_404():
    resp = client.put(
        "/api/investment-plans/99999",
        headers=_headers(),
        json={"amount": 200},
    )
    assert resp.status_code == 404


def test_delete_plan_404():
    resp = client.delete("/api/investment-plans/99999", headers=_headers())
    assert resp.status_code == 404


# ──────────────── upcoming ────────────────

def test_upcoming_executions_returns_future_only():
    _seed_fund()
    headers = _headers()
    # 每个工作日定投，从昨天开始 → 已经生成了未来执行行
    client.post(
        "/api/investment-plans",
        headers=headers,
        json={
            "fund_code": "005827",
            "plan_type": "daily",
            "amount": 200,
            "start_date": str(date.today() - timedelta(days=1)),
        },
    )

    resp = client.get("/api/investment-plans/upcoming?days_ahead=7", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    today = date.today()
    # 至少有今日（若是工作日）或下一个工作日
    assert all(date.fromisoformat(it["scheduled_date"]) >= today for it in items)
    if items:
        assert items[0]["fund_code"] == "005827"
        assert items[0]["plan_amount"] == 200


def test_upcoming_days_ahead_validation():
    headers = _headers()
    resp = client.get("/api/investment-plans/upcoming?days_ahead=0", headers=headers)
    assert resp.status_code == 422  # ge=1
    resp = client.get("/api/investment-plans/upcoming?days_ahead=100", headers=headers)
    assert resp.status_code == 422  # le=60


# ──────────────── smile-curve ────────────────

def test_smile_curve_for_missing_plan_returns_404():
    resp = client.get("/api/investment-plans/99999/smile-curve", headers=_headers())
    assert resp.status_code == 404


def test_smile_curve_empty_executions():
    _seed_fund()
    headers = _headers()
    plan = client.post(
        "/api/investment-plans",
        headers=headers,
        json={
            "fund_code": "005827",
            "plan_type": "monthly",
            "amount": 1000,
            "day_of_period": 15,
            "start_date": str(date.today()),
        },
    ).json()

    resp = client.get(f"/api/investment-plans/{plan['id']}/smile-curve", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["id"] == plan["id"]
    assert body["fund_name"] == "易方达蓝筹精选"
    assert body["execution_points"] == []
    assert body["summary"]["executed_periods"] == 0


# ──────────────── reconcile ────────────────

def test_reconcile_matches_buy_trade_to_execution():
    _seed_fund()
    headers = _headers()
    yesterday = date.today() - timedelta(days=1)

    plan = client.post(
        "/api/investment-plans",
        headers=headers,
        json={
            "fund_code": "005827",
            "plan_type": "daily",
            "amount": 200,
            "start_date": str(yesterday),
        },
    ).json()

    # 直接往 trades 表写一笔昨天的买入
    db = TestingSessionLocal()
    try:
        db.add(Trade(
            fund_code="005827",
            trade_type="买入",
            shares=100,
            nav_price=1.5,
            amount=150,
            trade_date=yesterday,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post(
        f"/api/investment-plans/{plan['id']}/reconcile",
        headers=headers,
    )
    assert resp.status_code == 200
    # 工作日才会匹配；若昨天是周末就跳过断言数量
    assert "matched" in resp.json()
    if yesterday.weekday() < 5:
        assert resp.json()["matched"] >= 1


def test_reconcile_404_for_missing_plan():
    resp = client.post(
        "/api/investment-plans/99999/reconcile",
        headers=_headers(),
    )
    assert resp.status_code == 404


# ──────────────── check-due ────────────────

def test_check_due_returns_summary_shape():
    headers = _headers()
    resp = client.post("/api/investment-plans/check-due", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    # 无论是否有到期任务，返回结构都应是稳定的
    assert "checked" in body
    assert "due_today" in body
    assert "notified" in body
    assert isinstance(body["due_today"], list)
