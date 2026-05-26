from .conftest import client


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_bootstrap_status():
    resp = client.get("/api/auth/bootstrap-status")
    assert resp.status_code == 200
    assert "has_user" in resp.json()


def test_setup_and_login():
    # 注册
    resp = client.post("/api/auth/setup", json={
        "username": "testuser", "password": "testpass123",
        "display_name": "测试用户",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "recovery_key" in data

    # 登录
    resp = client.post("/api/auth/login", json={
        "username": "testuser", "password": "testpass123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # 错误密码
    resp = client.post("/api/auth/login", json={
        "username": "testuser", "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_setup_duplicate():
    client.post("/api/auth/setup", json={
        "username": "dupuser", "password": "testpass123",
    })
    resp = client.post("/api/auth/setup", json={
        "username": "dupuser2", "password": "testpass123",
    })
    assert resp.status_code == 409


def test_token_refresh():
    # 注册并获取 refresh token
    resp = client.post("/api/auth/setup", json={
        "username": "refreshuser", "password": "testpass123",
    })
    # 登录获取 refresh token
    resp = client.post("/api/auth/login", json={
        "username": "refreshuser", "password": "testpass123",
        "remember_me": True,
    })
    data = resp.json()
    assert "refresh_token" in data

    # 用 refresh token 换新 token
    resp = client.post("/api/auth/refresh", headers={
        "X-Refresh-Token": data["refresh_token"],
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()
