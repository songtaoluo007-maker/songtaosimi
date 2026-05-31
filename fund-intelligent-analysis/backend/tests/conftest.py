import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.middleware import auth as auth_middleware
from backend.middleware import rate_limit as rate_limit_middleware


# 测试中跳过限流：单测可能在 1 分钟窗口内打数百个请求，没必要走 120/min 限制
_orig_rate_dispatch = rate_limit_middleware.RateLimitMiddleware.dispatch


async def _bypass_rate_limit(self, request, call_next):
    return await call_next(request)


rate_limit_middleware.RateLimitMiddleware.dispatch = _bypass_rate_limit

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    monkeypatch.setattr(auth_middleware, "SessionLocal", TestingSessionLocal)
    auth_middleware.LocalAuthMiddleware.clear_count_cache()
    Base.metadata.create_all(bind=engine)
    yield
    auth_middleware.LocalAuthMiddleware.clear_count_cache()
    Base.metadata.drop_all(bind=engine)


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def register_and_login(username: str = "endpoint_user", password: str = "testpass123") -> str:
    """注册一个用户并返回 access_token；供端点测试套件复用。"""
    resp = client.post("/api/auth/setup", json={
        "username": username, "password": password,
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    # 已存在 → 走 login
    resp = client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers() -> dict:
    token = register_and_login()
    return {"Authorization": f"Bearer {token}"}
