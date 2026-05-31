"""
/api/user/profile 端点测试 — P1.3
"""
from datetime import date

from .conftest import client, register_and_login


def _headers():
    return {"Authorization": f"Bearer {register_and_login()}"}


# ──────────────── 鉴权 ────────────────

def test_profile_requires_auth():
    resp = client.get("/api/user/profile")
    assert resp.status_code == 401


# ──────────────── GET 默认空状态 ────────────────

def test_get_profile_returns_empty_fields_for_new_user():
    resp = client.get("/api/user/profile", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    # 新用户所有画像字段都应为 None / 默认值
    assert body["birth_year"] is None
    assert body["risk_appetite"] is None
    assert body["profile_notes"] == ""


# ──────────────── PUT 校验 ────────────────

def test_put_profile_rejects_bad_purpose():
    resp = client.put(
        "/api/user/profile",
        headers=_headers(),
        json={"funds_purpose": "vacation"},  # 非法
    )
    assert resp.status_code == 400
    assert "funds_purpose" in resp.json()["detail"]


def test_put_profile_rejects_bad_risk_appetite():
    resp = client.put(
        "/api/user/profile",
        headers=_headers(),
        json={"risk_appetite": "yolo"},  # 非法
    )
    assert resp.status_code == 400
    assert "risk_appetite" in resp.json()["detail"]


# ──────────────── PUT happy path ────────────────

def test_put_profile_updates_and_persists():
    headers = _headers()
    payload = {
        "birth_year": 1985,
        "retirement_target_year": 2055,
        "investment_horizon_years": 20,
        "funds_purpose": "retirement",
        "target_annual_return": 8.0,
        "max_acceptable_drawdown": 25.0,
        "risk_appetite": "balanced",
        "monthly_disposable_income": 5000,
        "profile_notes": "稳健派",
        # 不允许的额外字段应该被忽略
        "username": "haha",
    }
    resp = client.put("/api/user/profile", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["birth_year"] == 1985
    assert body["funds_purpose"] == "retirement"
    assert body["target_annual_return"] == 8.0
    assert body["profile_notes"] == "稳健派"
    assert body["profile_updated_at"]  # 写入了时间戳

    # GET 应回同样的值
    resp = client.get("/api/user/profile", headers=headers)
    assert resp.json()["risk_appetite"] == "balanced"


# ──────────────── recommend-allocation ────────────────

def test_recommend_allocation_uses_profile():
    headers = _headers()
    # 先填一份画像：1985 年生（约 40 岁）+ 退休 + balanced
    client.put(
        "/api/user/profile",
        headers=headers,
        json={
            "birth_year": 1985,
            "funds_purpose": "retirement",
            "risk_appetite": "balanced",
        },
    )
    resp = client.post(
        "/api/user/profile/recommend-allocation",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["age"] == date.today().year - 1985
    assert body["purpose"] == "retirement"
    assert body["risk_appetite"] == "balanced"

    # 推荐应包含 5 个资产大类
    classes = {it["asset_class"] for it in body["recommendation"]}
    assert classes == {"equity_a", "equity_us", "bond", "gold", "cash"}

    # 总和接近 100%（允许小数舍入误差）
    total = sum(it["target_pct"] for it in body["recommendation"])
    assert abs(total - 100) <= 1.0


def test_recommend_allocation_conservative_lowers_equity():
    headers = _headers()
    client.put(
        "/api/user/profile",
        headers=headers,
        json={
            "birth_year": 1985,
            "funds_purpose": "long_term",
            "risk_appetite": "conservative",
        },
    )
    cons = client.post(
        "/api/user/profile/recommend-allocation", headers=headers,
    ).json()

    client.put(
        "/api/user/profile",
        headers=headers,
        json={"risk_appetite": "aggressive"},
    )
    aggr = client.post(
        "/api/user/profile/recommend-allocation", headers=headers,
    ).json()

    # 激进偏好的权益占比应高于保守
    cons_eq = next(it for it in cons["recommendation"] if it["asset_class"] == "equity_a")["target_pct"]
    aggr_eq = next(it for it in aggr["recommendation"] if it["asset_class"] == "equity_a")["target_pct"]
    assert aggr_eq > cons_eq


def test_recommend_allocation_no_birth_year_uses_defaults():
    headers = _headers()
    # 不填 birth_year
    resp = client.post(
        "/api/user/profile/recommend-allocation",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["age"] is None
    assert "参考起点" in body["reasoning"]
