"""
API 频率限制中间件 — V2

V2 改动：
- 支持 X-Forwarded-For 解析（pywebview / 反向代理场景下，原 v1 全部限制到 127.0.0.1）
- 增加白名单豁免（/api/health、静态 OCR 等高频但安全端点）
- 自动定期清理空 IP 槽，避免内存随时间累积
- 429 响应增加 Retry-After 头，方便前端 axios 友好降级
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

WHITELIST_PATHS = {"/api/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 120,
        window: int = 60,
        cleanup_interval: int = 300,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self.cleanup_interval = cleanup_interval
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._last_cleanup: float = time.time()

    def _resolve_client_ip(self, request) -> str:
        # 优先 X-Forwarded-For（取第一个 IP），再 X-Real-IP，最后回退 request.client
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",", 1)[0].strip()
        xri = request.headers.get("X-Real-IP", "")
        if xri:
            return xri.strip()
        return request.client.host if request.client else "unknown"

    async def _periodic_cleanup(self, now: float, cutoff: float) -> None:
        if now - self._last_cleanup < self.cleanup_interval:
            return
        empty_keys = [k for k, ts_list in self._store.items() if not [t for t in ts_list if t > cutoff]]
        for k in empty_keys:
            self._store.pop(k, None)
        self._last_cleanup = now

    async def dispatch(self, request, call_next):
        if request.url.path in WHITELIST_PATHS:
            return await call_next(request)

        ip = self._resolve_client_ip(request)
        now = time.time()
        cutoff = now - self.window

        async with self._lock:
            recent = [t for t in self._store[ip] if t > cutoff]
            if len(recent) >= self.max_requests:
                retry_after = max(1, int(self.window - (now - recent[0])))
                return JSONResponse(
                    {"detail": "请求过于频繁，请稍后重试"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
            recent.append(now)
            self._store[ip] = recent
            await self._periodic_cleanup(now, cutoff)

        return await call_next(request)
