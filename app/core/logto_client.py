"""
Logto client configuration and session storage implementation for FastAPI.
"""
from typing import Union, Optional
from logto import LogtoClient, LogtoConfig, Storage
from fastapi import Request, Response
from app.core.config import settings
import json
import logging

logger = logging.getLogger(__name__)


class FastAPISessionStorage(Storage):
    """
    Session storage implementation for Logto using FastAPI request/response.
    This stores Logto session data in HTTP cookies.
    """
    
    def __init__(self, request: Request, response: Response):
        self.request = request
        self.response = response
        self._session_key = "logto_session"
    
    def get(self, key: str) -> Union[str, None]:
        """Get a value from the session storage."""
        try:
            # Get session data from cookie
            session_data = self.request.cookies.get(self._session_key)
            logger.debug(f"Getting session key '{key}', session_data exists: {session_data is not None}")

            if not session_data:
                return None

            # Parse JSON data
            session_dict = json.loads(session_data)
            value = session_dict.get(key)
            logger.debug(f"Session key '{key}' value: {value is not None}")
            return value
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse session JSON for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get session key {key}: {e}")
            return None
    
    def set(self, key: str, value: Union[str, None]) -> None:
        """Set a value in the session storage."""
        try:
            # Get existing session data
            session_data = self.request.cookies.get(self._session_key, "{}")
            session_dict = json.loads(session_data) if session_data else {}

            logger.debug(f"Setting session key '{key}', value exists: {value is not None}")

            # Update the value
            if value is None:
                session_dict.pop(key, None)
                logger.debug(f"Removed session key '{key}'")
            else:
                session_dict[key] = value
                logger.debug(f"Set session key '{key}' with value length: {len(str(value))}")

            # Save back to cookie
            session_json = json.dumps(session_dict)

            # Use simpler cookie settings for development
            self.response.set_cookie(
                key=self._session_key,
                value=session_json,
                httponly=False,  # Allow JavaScript access for debugging
                secure=False,  # Don't require HTTPS in development
                samesite="lax",  # More permissive for development
                max_age=86400,  # 1 day
                path="/",  # Ensure cookie is available for all paths
            )
            logger.debug(f"Session cookie set with {len(session_dict)} keys, cookie size: {len(session_json)} bytes")

        except Exception as e:
            logger.error(f"Failed to set session key {key}: {e}")
    
    def delete(self, key: str) -> None:
        """Delete a value from the session storage."""
        self.set(key, None)


def create_logto_client(request: Request, response: Response) -> Optional[LogtoClient]:
    """
    Create a Logto client with session storage.
    Returns None if Logto is not configured.
    """
    if not all([settings.LOGTO_ENDPOINT, settings.LOGTO_APP_ID, settings.LOGTO_APP_SECRET]):
        logger.warning("Logto configuration incomplete. Skipping Logto client creation.")
        return None

    try:
        logger.debug(f"Creating Logto client with endpoint: {settings.LOGTO_ENDPOINT}")
        logger.debug(f"Request cookies: {list(request.cookies.keys())}")

        config = LogtoConfig(
            endpoint=settings.LOGTO_ENDPOINT,
            appId=settings.LOGTO_APP_ID,
            appSecret=settings.LOGTO_APP_SECRET,
        )

        storage = FastAPISessionStorage(request, response)

        client = LogtoClient(config, storage=storage)
        logger.debug("Logto client created successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to create Logto client: {e}")
        return None


def get_logto_config() -> dict:
    """Get Logto configuration for frontend."""
    return {
        "endpoint": settings.LOGTO_ENDPOINT,
        "appId": settings.LOGTO_APP_ID,
        "redirectUri": settings.LOGTO_REDIRECT_URI,
        "postLogoutRedirectUri": settings.LOGTO_POST_LOGOUT_REDIRECT_URI,
    }
