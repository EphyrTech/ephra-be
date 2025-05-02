from fastapi import Request, Response
import time
from typing import Dict, Tuple, Optional
import hashlib
import json
import logging

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("middleware.cache")

class CacheMiddleware:
    """
    Caching middleware for FastAPI.
    
    Caches responses for GET requests to improve performance.
    """
    def __init__(self, ttl_seconds: int = None):
        self.ttl_seconds = ttl_seconds or settings.CACHE_TTL_SECONDS
        self.cache: Dict[str, Tuple[float, Response]] = {}  # key -> (expiry, response)
        logger.info(f"Cache middleware initialized with TTL of {self.ttl_seconds} seconds")
    
    def _get_cache_key(self, request: Request) -> Optional[str]:
        """
        Generate a cache key from the request.
        
        Args:
            request (Request): The FastAPI request
            
        Returns:
            Optional[str]: Cache key or None if request should not be cached
        """
        # Only cache GET requests
        if request.method != "GET":
            return None
        
        # Don't cache authenticated requests
        if "authorization" in request.headers:
            return None
        
        # Don't cache certain paths
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc") or request.url.path.startswith("/openapi.json"):
            return None
        
        # Create a hash of the path and query parameters
        key_parts = [request.url.path]
        key_parts.extend(sorted([f"{k}={v}" for k, v in request.query_params.items()]))
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def __call__(self, request: Request, call_next):
        # Get cache key
        cache_key = self._get_cache_key(request)
        
        # If not cacheable, just process the request
        if not cache_key:
            return await call_next(request)
        
        # Check if we have a cached response
        current_time = time.time()
        if cache_key in self.cache:
            expiry, cached_response = self.cache[cache_key]
            if current_time < expiry:
                logger.debug(f"Cache hit for {request.url.path}")
                return cached_response
            # Expired, remove from cache
            logger.debug(f"Cache expired for {request.url.path}")
            del self.cache[cache_key]
        
        # Process the request
        response = await call_next(request)
        
        # Cache the response if it's successful
        if 200 <= response.status_code < 300:
            # We need to create a new response to cache
            # because the original will be consumed
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Create a new response with the same data
            cached_response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            
            # Store in cache
            self.cache[cache_key] = (current_time + self.ttl_seconds, cached_response)
            logger.debug(f"Cached response for {request.url.path}")
            
            # Return a new response with the same body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        return response
