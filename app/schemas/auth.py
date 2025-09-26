from pydantic import BaseModel, field_validator, Field
from typing import Optional, TYPE_CHECKING, Any, Dict, List

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

class AuthInfo(BaseModel):
    sub: str
    client_id: Optional[str] = None
    organization_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    audience: List[str] = Field(default_factory=list)

    # verify if user has any of the scopes using pydantic
    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope."""
        return scope in self.scopes

    def has_any_scope(self, scopes: List[str]) -> bool:
        """Check if user has any of the specified scopes."""
        return any(s in self.scopes for s in scopes)

    def has_all_scopes(self, scopes: List[str]) -> bool:
        """Check if user has all of the specified scopes."""
        return all(s in self.scopes for s in scopes)

    def to_dict(self) -> dict:
        return self.model_dump()