"""
Logto configuration utilities for FastAPI.
This module provides configuration for frontend Logto integration.
"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_logto_config() -> dict:
    """
    Get Logto configuration for frontend.
    Note: redirectUri and postLogoutRedirectUri are determined dynamically by the frontend.
    The backend only provides the endpoint and appId for JWT validation.
    """
    if not settings.LOGTO_APP_ID:
        logger.warning("LOGTO_APP_ID is not configured")

    return {
        "endpoint": settings.LOGTO_ENDPOINT,
        "appId": settings.LOGTO_FE_APP_ID,
        # Note: Redirect URIs are handled dynamically by the frontend
        # The backend only validates JWT tokens, not redirect flows
    }
