"""
本地认证中间件 — V2

V2 改动：
- 用模块级 Lock 保护 _user_count_cache，避免多线程并发同时打 SETUP_REQUIRED DB 查
- 把 user_count 缓存做成 (count, checked_at) 的小元组，clear_count_cache 改用赋值而非全局 flag
- 缓存 TTL 30s：用户首次完成 setup 后无需重启，30s 内自动放行
- 维持原 BaseHTTPMiddleware 行为；保留 OPTIONS / PUBLIC 白名单
"""
from __future__ import annotations

import time
from threading import Lock

from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from backend.database import SessionLocal
from backend.services.auth_service import get_user_from_token, user_count

PUBLIC_API_PATHS = {
    "/api/health",
    "/api/auth/bootstrap-status",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/recover",
    "/api/auth/recovery-key-status",
}

_CACHE_TTL_SECONDS = 30
_cache_lock = Lock()
_user_count_cache: int | None = None
_cache_checked_at: float = 0.0


def _get_user_count() -> int:
    global _user_count_cache, _cache_checked_at
    now = time.time()
    with _cache_lock:
        if (
            _user_count_cache is not None
            and _user_count_cache > 0
            and now - _cache_checked_at < _CACHE_TTL_SECONDS
        ):
            return _user_count_cache

    # 锁外查 DB，避免在持锁状态下做 IO
    db = SessionLocal()
    try:
        fresh_count = user_count(db)
    finally:
        db.close()

    with _cache_lock:
        _user_count_cache = fresh_count
        _cache_checked_at = time.time()
        return fresh_count


class LocalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api/")
            or path in PUBLIC_API_PATHS
        ):
            return await call_next(request)

        if _get_user_count() == 0:
            return JSONResponse({"detail": "SETUP_REQUIRED"}, status_code=401)

        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            return JSONResponse({"detail": "UNAUTHORIZED"}, status_code=401)
        token = authorization.split(" ", 1)[1].strip()

        db = SessionLocal()
        try:
            user = get_user_from_token(db, token)
            request.state.user = user.to_public_dict()
        except (ValueError, IndexError, KeyError, TypeError):
            return JSONResponse({"detail": "UNAUTHORIZED"}, status_code=401)
        except Exception:
            logger.exception(f"认证中间件异常 {request.method} {path}")
            return JSONResponse({"detail": "INTERNAL_ERROR"}, status_code=500)
        finally:
            db.close()

        return await call_next(request)

    @staticmethod
    def clear_count_cache() -> None:
        """密码重置 / 用户变更后调用，强制下一次请求重新查 DB。"""
        global _user_count_cache, _cache_checked_at
        with _cache_lock:
            _user_count_cache = None
            _cache_checked_at = 0.0
