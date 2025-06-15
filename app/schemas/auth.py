from pydantic import BaseModel, field_validator
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.user import User as UserSchema

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

class Login(BaseModel):
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        # Import here to avoid circular imports
        from app.schemas.user import validate_email_field
        return validate_email_field(v)

class GoogleAuth(BaseModel):
    token: str

class PasswordReset(BaseModel):
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        # Import here to avoid circular imports
        from app.schemas.user import validate_email_field
        return validate_email_field(v)

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class LogtoUserInfo(BaseModel):
    """Schema for Logto user information."""
    sub: str  # Logto user ID
    email: Optional[str] = None
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    phone_number: Optional[str] = None

class LogtoAuthResponse(BaseModel):
    """Response after successful Logto authentication."""
    user: dict  # We'll use dict instead of forward reference for now
    access_token: str
    token_type: str = "bearer"

class LogtoConfig(BaseModel):
    """Logto configuration for frontend."""
    endpoint: str
    appId: str
    # Note: redirectUri and postLogoutRedirectUri are now handled dynamically by the frontend
    redirectUri: Optional[str] = None
    postLogoutRedirectUri: Optional[str] = None
