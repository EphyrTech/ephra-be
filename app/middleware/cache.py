import hashlib
import logging
import time
from typing import Dict, Optional, Tuple

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("middleware.cache")

# Global cache instance for access from other modules
_cache_instance: Optional['CacheMiddleware'] = None

def get_cache_instance() -> Optional['CacheMiddleware']:
    """Get the global cache instance"""
    return _cache_instance

def invalidate_cache(pattern: Optional[str] = None):
    """Utility function to invalidate cache from anywhere in the application"""
    if _cache_instance:
        _cache_instance.clear_cache(pattern)
    else:
        logger.warning("Cache instance not available for invalidation")

class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, ttl_seconds: Optional[int] = None):
        super().__init__(app)
        self.ttl_seconds = ttl_seconds or settings.CACHE_TTL_SECONDS
        self.cache: Dict[str, Tuple[float, Response]] = {}
        logger.info(f"Cache middleware initialized with TTL of {self.ttl_seconds} seconds")

        # Set global instance
        global _cache_instance
        _cache_instance = self

    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries. If pattern is provided, only clear matching entries."""
        if pattern is None:
            # Clear all cache
            self.cache.clear()
            logger.info("Cache cleared completely")
        else:
            # Clear cache entries matching pattern
            keys_to_remove = []
            for key in self.cache.keys():
                # Since keys are hashed, we need to check the original paths
                # For now, we'll clear all cache when pattern is provided
                keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Cache cleared for pattern: {pattern}")

    def invalidate_admin_cache(self):
        """Invalidate all admin-related cache entries"""
        self.clear_cache("admin")  # This will clear all cache for now

    def _get_cache_key(self, request: Request) -> Optional[str]:
        if request.method != "GET":
            return None
        if "authorization" in request.headers:
            return None
        # Don't cache admin panel pages (they use session cookies, not auth headers)
        if request.url.path.startswith(("/docs", "/redoc", "/openapi.json", "/admin-control-panel-x7k9m2")):
            return None
        # Don't cache if there are session cookies (admin panel)
        if "admin_session_id" in request.cookies:
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
