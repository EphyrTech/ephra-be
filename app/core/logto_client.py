"""
Logto configuration utilities for FastAPI.
This module provides configuration for frontend Logto integration.
"""
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_logto_config() -> dict:
    """Get Logto configuration for frontend."""
    return {
        "endpoint": settings.LOGTO_ENDPOINT,
        "appId": settings.LOGTO_APP_ID,
        "redirectUri": settings.LOGTO_REDIRECT_URI,
        "postLogoutRedirectUri": settings.LOGTO_POST_LOGOUT_REDIRECT_URI,
    }
