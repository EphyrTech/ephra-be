"""
FastAPI authentication middleware for Logto JWT validation.
Based on the official Logto FastAPI integration guide.
"""
import logging
from typing import Any, Dict

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from app.db.database import get_db
from app.schemas.auth import AuthInfo

from app.services.logto_service import LogtoManagerService
from app.core.rbac import RoleScopes

from app.core.config import settings

logger = logging.getLogger(__name__)

# Validate Logto configuration
def validate_logto_config():
    """Validate that required Logto configuration is present."""
    missing_configs = []

    if not settings.LOGTO_ENDPOINT:
        missing_configs.append("LOGTO_ENDPOINT")
    if not settings.LOGTO_APP_ID:
        missing_configs.append("LOGTO_APP_ID")
    if not settings.LOGTO_API_RESOURCE:
        missing_configs.append("LOGTO_API_RESOURCE")

    if missing_configs:
        logger.error(f"Missing required Logto configuration: {', '.join(missing_configs)}")
        return False

    logger.info(f"Logto configuration validated - App ID: {settings.LOGTO_APP_ID}, API Resource: {settings.LOGTO_API_RESOURCE}")
    return True

# Initialize JWKS client for JWT validation
jwks_client = None
if settings.LOGTO_ENDPOINT and validate_logto_config():
    # Remove trailing slash to avoid double slashes
    endpoint = settings.LOGTO_ENDPOINT.rstrip('/')
    JWKS_URI = f'{endpoint}/oidc/jwks'
    ISSUER = f'{endpoint}/oidc'
    jwks_client = PyJWKClient(JWKS_URI)
    logger.info(f"Initialized JWKS client for endpoint: {endpoint}")
else:
    logger.warning("Logto authentication is not properly configured - JWT validation will fail")

security = HTTPBearer()

class AuthorizationError(Exception):
    """Custom exception for authorization errors."""
    
    def __init__(self, message: str, status: int = 403):
        self.message = message
        self.status = status
        super().__init__(self.message)


def validate_jwt(token: str) -> Dict[str, Any]:
    """Validate JWT and return payload."""
    if not jwks_client:
        raise AuthorizationError('Logto authentication is not configured', 503)
    
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode with full validation
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256', 'ES256', 'ES384', 'ES512'],  # Support multiple algorithms
            issuer=ISSUER,
            options={'verify_aud': False}  # We'll verify audience manually
        )
        verify_payload(payload)
        return payload
    except jwt.InvalidTokenError as e:
        raise AuthorizationError(f'Invalid token: {str(e)}', 401)
    except Exception as e:
        raise AuthorizationError(f'Token validation failed: {str(e)}', 401)


def create_auth_info(payload: Dict[str, Any]) -> AuthInfo:
    """Create AuthInfo from JWT payload."""
    # Extract and clean scopes
    scope_string = payload.get('scope', '')
    if scope_string:
        # Split by space and filter out empty strings
        scopes = [scope.strip() for scope in scope_string.split(' ') if scope.strip()]
    else:
        scopes = []

    # Handle audience field
    audience = payload.get('aud', [])
    if isinstance(audience, str):
        audience = [audience]

    # Validate required subject field
    sub = payload.get('sub')
    if not sub:
        raise AuthorizationError('Token missing subject (sub) claim')

    auth_info = AuthInfo(
        sub=sub,
        client_id=payload.get('client_id'),
        organization_id=payload.get('organization_id'),
        scopes=scopes,
        audience=audience
    )

    if not auth_info.has_any_scope(RoleScopes.ADMIN):
        raise AuthorizationError('User does not have required scopes', 403)

    return auth_info


def verify_payload(payload: Dict[str, Any]) -> None:
    """Verify payload based on permission model."""
    # Validate required fields
    if not payload.get('sub'):
        raise AuthorizationError('Token missing subject (sub) claim')


    # Check if token has required audience (API resource)
    audiences = payload.get('aud', [])
    if isinstance(audiences, str):
        audiences = [audiences]

    if settings.LOGTO_API_RESOURCE not in audiences:
        raise AuthorizationError(f'Invalid audience. Expected: {settings.LOGTO_API_RESOURCE}')
    
    logger.debug(f"Token validated for subject: {payload.get('sub')} with scopes: {payload.get('scope', 'none')} from client: {payload.get('client_id')}")



async def verify_access_token(db = Depends(get_db),credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthInfo:
    """Verify access token and return authentication info."""
    try:
        token = credentials.credentials
        payload = validate_jwt(token)
        return create_auth_info(payload)
    except AuthorizationError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


# Optional: Create a dependency for specific scopes
def require_scopes(*required_scopes: str):
    """Create a dependency that requires specific scopes."""
    async def check_scopes(auth: AuthInfo = Depends(verify_access_token)) -> AuthInfo:
        if required_scopes:
            missing_scopes = [scope for scope in required_scopes if scope not in auth.scopes]
            if missing_scopes:
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing required scopes: {', '.join(missing_scopes)}"
                )
        return auth
    return check_scopes


# Optional: Create a dependency for organization context
def require_organization(organization_id: str = None):
    """Create a dependency that requires organization context."""
    async def check_organization(auth: AuthInfo = Depends(verify_access_token)) -> AuthInfo:
        if organization_id and auth.organization_id != organization_id:
            raise HTTPException(
                status_code=403,
                detail="Organization context mismatch"
            )
        return auth
    return check_organization
