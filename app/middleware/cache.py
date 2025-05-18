from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import Response
import time
from typing import Dict, Tuple, Optional
import hashlib
import logging

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("middleware.cache")

class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, ttl_seconds: int = None):
        super().__init__(app)
        self.ttl_seconds = ttl_seconds or settings.CACHE_TTL_SECONDS
        self.cache: Dict[str, Tuple[float, Response]] = {}
        logger.info(f"Cache middleware initialized with TTL of {self.ttl_seconds} seconds")

    def _get_cache_key(self, request: Request) -> Optional[str]:
        if request.method != "GET":
            return None
        if "authorization" in request.headers:
            return None
        if request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            return None
        key_parts = [request.url.path]
        key_parts.extend(sorted([f"{k}={v}" for k, v in request.query_params.items()]))
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    async def dispatch(self, request: Request, call_next):
        cache_key = self._get_cache_key(request)
        if not cache_key:
            return await call_next(request)

        current_time = time.time()
        if cache_key in self.cache:
            expiry, cached_response = self.cache[cache_key]
            if current_time < expiry:
                logger.debug(f"Cache hit for {request.url.path}")
                return cached_response
            else:
                logger.debug(f"Cache expired for {request.url.path}")
                del self.cache[cache_key]

        response = await call_next(request)

        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            cached_response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

            self.cache[cache_key] = (current_time + self.ttl_seconds, cached_response)

            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        return response
