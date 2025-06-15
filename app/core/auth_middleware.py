"""
FastAPI authentication middleware for Logto JWT validation.
Based on the official Logto FastAPI integration guide.
"""
from typing import Dict, Any, List, Optional
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize JWKS client for JWT validation
jwks_client = None
if settings.LOGTO_ENDPOINT:
    JWKS_URI = f'{settings.LOGTO_ENDPOINT}/oidc/jwks'
    ISSUER = f'{settings.LOGTO_ENDPOINT}/oidc'
    jwks_client = PyJWKClient(JWKS_URI)

security = HTTPBearer()


class AuthInfo:
    """Authentication information extracted from JWT token."""
    
    def __init__(self, sub: str, client_id: str = None, organization_id: str = None,
                 scopes: List[str] = None, audience: List[str] = None):
        self.sub = sub
        self.client_id = client_id
        self.organization_id = organization_id
        self.scopes = scopes or []
        self.audience = audience or []

    def to_dict(self):
        return {
            'sub': self.sub,
            'client_id': self.client_id,
            'organization_id': self.organization_id,
            'scopes': self.scopes,
            'audience': self.audience
        }


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

        # First decode without issuer validation to see what's in the token
        payload_unverified = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256', 'ES256', 'ES384', 'ES512'],
            options={'verify_signature': False, 'verify_aud': False, 'verify_iss': False}
        )

        print(f"Expected issuer: {ISSUER}")
        print(f"Token issuer: {payload_unverified.get('iss', 'NOT_FOUND')}")

        # Now decode with full validation
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
    scopes = payload.get('scope', '').split(' ') if payload.get('scope') else []
    audience = payload.get('aud', [])
    if isinstance(audience, str):
        audience = [audience]
    
    return AuthInfo(
        sub=payload.get('sub'),
        client_id=payload.get('client_id'),
        organization_id=payload.get('organization_id'),
        scopes=scopes,
        audience=audience
    )


def verify_payload(payload: Dict[str, Any]) -> None:
    """Verify payload based on permission model."""
    # For now, we'll implement basic validation
    # This can be extended based on your specific permission model
    
    # Check if token has required audience (if configured)
    if hasattr(settings, 'LOGTO_API_RESOURCE') and settings.LOGTO_API_RESOURCE:
        audiences = payload.get('aud', [])
        if isinstance(audiences, str):
            audiences = [audiences]
        
        if settings.LOGTO_API_RESOURCE not in audiences:
            raise AuthorizationError('Invalid audience')
    
    # Additional validation can be added here based on your needs
    logger.debug(f"Token validated for subject: {payload.get('sub')}")


async def verify_access_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthInfo:
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
