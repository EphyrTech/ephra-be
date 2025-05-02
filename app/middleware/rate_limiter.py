from fastapi import Request, Response, status
import time
from typing import Dict, Tuple
import logging

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("middleware.rate_limiter")

class RateLimiter:
    """
    Rate limiting middleware for FastAPI.
    
    Limits the number of requests per minute per client IP.
    """
    def __init__(self, requests_per_minute: int = None):
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.clients: Dict[str, Tuple[int, float]] = {}  # IP -> (count, start_time)
        logger.info(f"Rate limiter initialized with {self.requests_per_minute} requests per minute")
        
    async def __call__(self, request: Request, call_next):
        # Skip rate limiting for certain paths
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc") or request.url.path.startswith("/openapi.json"):
            return await call_next(request)
        
        client_ip = request.client.host
        current_time = time.time()
        
        # Get or create client record
        if client_ip not in self.clients:
            self.clients[client_ip] = (1, current_time)
        else:
            count, start_time = self.clients[client_ip]
            
            # Reset counter if a minute has passed
            if current_time - start_time > 60:
                self.clients[client_ip] = (1, current_time)
            else:
                # Increment counter
                count += 1
                if count > self.requests_per_minute:
                    logger.warning(f"Rate limit exceeded for {client_ip}")
                    return Response(
                        content={"message": "Rate limit exceeded. Please try again later."},
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        media_type="application/json"
                    )
                self.clients[client_ip] = (count, start_time)
        
        return await call_next(request)
