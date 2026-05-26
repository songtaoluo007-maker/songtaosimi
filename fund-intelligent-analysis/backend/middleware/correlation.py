import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        correlation_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.correlation_id = correlation_id
        with logger.contextualize(request_id=correlation_id):
            response = await call_next(request)
            response.headers["X-Request-ID"] = correlation_id
            return response
