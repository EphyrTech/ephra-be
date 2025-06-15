from pydantic import BaseModel, Field, field_validator, model_serializer
from typing import Optional, Union
from datetime import datetime, date
from enum import Enum
import re
from app.core.config import settings

class UserRole(str, Enum):
    USER = "user"
    CARE_PROVIDER = "care_provider"
    ADMIN = "admin"


def validate_email_field(email: str) -> str:
    """
    Custom email validator that allows .local domains in development.
    In production, uses strict email validation.
    """
    if not email:
        return email

    # In development, allow .local domains (common with Logto test environments)
    if settings.ENVIRONMENT == "development" and email.endswith("@logto.local"):
        # Convert .local emails to a valid domain for development
        username = email.split("@")[0]
        return f"{username}@ephyrtech.com"

    # Basic email format validation using regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, email):
        # Email looks valid, return as-is
        return email

    # If email format is invalid
    if settings.ENVIRONMENT == "development":
        # In development mode, create a fallback
        username_part = re.sub(r'[^a-zA-Z0-9_.-]', '', email.split("@")[0] if "@" in email else email)
        return f"{username_part}@ephyrtech.com"
    else:
        # In production, raise an error for invalid emails
        raise ValueError(f"Invalid email format: {email}")

# Shared properties
class UserBase(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[UserRole] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_email_field(v)

# Properties to receive via API on creation
class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_field(v)

# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None

# Properties to return via API
class User(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @model_serializer
    def serialize_model(self) -> dict:
        """Custom serializer to handle email conversion during output."""
        data = {
            'id': self.id,
            'email': validate_email_field(self.email) if self.email else self.email,
            'name': self.name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'display_name': self.display_name,
            'photo_url': self.photo_url,
            'date_of_birth': self.date_of_birth,
            'country': self.country,
            'phone_number': self.phone_number,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
        return data

# Properties stored in DB
class UserInDB(User):
    hashed_password: str

# Schema for account deletion
class AccountDeletion(BaseModel):
    password: str

# Schema for email update
class EmailUpdate(BaseModel):
    new_email: str
    password: str

    @field_validator('new_email')
    @classmethod
    def validate_new_email(cls, v: str) -> str:
        return validate_email_field(v)
