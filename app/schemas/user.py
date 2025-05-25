from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    CARE_PROVIDER = "care_provider"
    ADMIN = "admin"

# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[UserRole] = None

# Properties to receive via API on creation
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None

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

# Properties stored in DB
class UserInDB(User):
    hashed_password: str

# Schema for account deletion
class AccountDeletion(BaseModel):
    password: str

# Schema for email update
class EmailUpdate(BaseModel):
    new_email: EmailStr
    password: str
