"""基金管理 API 测试"""
from .conftest import client


def _setup_and_login():
    """Helper: create a user and return auth headers."""
    client.post("/api/auth/setup", json={
        "username": "fundtester", "password": "testpass123",
    })
    resp = client.post("/api/auth/login", json={
        "username": "fundtester", "password": "testpass123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_funds_empty():
    headers = _setup_and_login()
    resp = client.get("/api/funds", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_add_fund():
    headers = _setup_and_login()
    resp = client.post("/api/funds", json={
        "fund_code": "005827",
        "fund_name": "易方达蓝筹精选",
        "fund_type": "混合型",
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["fund_code"] == "005827"


def test_get_fund():
    headers = _setup_and_login()
    client.post("/api/funds", json={
        "fund_code": "005827", "fund_name": "易方达蓝筹精选",
    }, headers=headers)
    resp = client.get("/api/funds/005827", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["fund_name"] == "易方达蓝筹精选"


def test_get_fund_not_found():
    headers = _setup_and_login()
    resp = client.get("/api/funds/999999", headers=headers)
    assert resp.status_code == 404


def test_search_fund_invalid_code():
    headers = _setup_and_login()
    resp = client.get("/api/funds/search/12345", headers=headers)
    assert resp.status_code == 400


def test_delete_fund():
    headers = _setup_and_login()
    client.post("/api/funds", json={
        "fund_code": "161725", "fund_name": "招商中证白酒",
    }, headers=headers)
    resp = client.delete("/api/funds/161725", headers=headers)
    assert resp.status_code == 200
    # verify deleted
    resp = client.get("/api/funds/161725", headers=headers)
    assert resp.status_code == 404


def test_list_funds_with_filter():
    headers = _setup_and_login()
    client.post("/api/funds", json={
        "fund_code": "000001", "fund_name": "华夏成长", "fund_type": "混合型",
    }, headers=headers)
    client.post("/api/funds", json={
        "fund_code": "000002", "fund_name": "某债券基金", "fund_type": "债券型",
    }, headers=headers)
    resp = client.get("/api/funds?fund_type=债券型", headers=headers)
    assert resp.status_code == 200
    funds = resp.json()
    assert all(f["fund_type"] == "债券型" for f in funds)
