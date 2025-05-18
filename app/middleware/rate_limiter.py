from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import Response, status
import time
from typing import Dict, Tuple
import logging

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("middleware.rate_limiter")

class RateLimiter(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.clients: Dict[str, Tuple[int, float]] = {}
        logger.info(f"Rate limiter initialized with {self.requests_per_minute} requests per minute")

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        client_ip = request.client.host
        current_time = time.time()

        count, start_time = self.clients.get(client_ip, (0, current_time))

        if current_time - start_time > 60:
            # reset window
            self.clients[client_ip] = (1, current_time)
        else:
            count += 1
            if count > self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return Response(
                    content='{"message": "Rate limit exceeded. Please try again later."}',
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    media_type="application/json"
                )
            self.clients[client_ip] = (count, start_time)

        return await call_next(request)
