"""Schemas for care provider profiles"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class SpecialistType(str, Enum):
    MENTAL = "mental"
    PHYSICAL = "physical"

# Base schema
class CareProviderProfileBase(BaseModel):
    specialty: SpecialistType = Field(..., description="Care provider specialty")
    bio: Optional[str] = Field(None, description="Professional bio")
    hourly_rate: Optional[int] = Field(None, description="Hourly rate in cents")
    license_number: Optional[str] = Field(None, description="Professional license number")
    years_experience: Optional[int] = Field(None, description="Years of experience")
    education: Optional[str] = Field(None, description="Educational background")
    certifications: Optional[str] = Field(None, description="Professional certifications")
    is_accepting_patients: Optional[bool] = Field(True, description="Whether accepting new patients")

# Schema for creating care provider profile
class CareProviderProfileCreate(CareProviderProfileBase):
    pass

# Schema for updating care provider profile
class CareProviderProfileUpdate(BaseModel):
    specialty: Optional[SpecialistType] = None
    bio: Optional[str] = None
    hourly_rate: Optional[int] = None
    license_number: Optional[str] = None
    years_experience: Optional[int] = None
    education: Optional[str] = None
    certifications: Optional[str] = None
    is_accepting_patients: Optional[bool] = None

# Schema for returning care provider profile
class CareProviderProfile(CareProviderProfileBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema for care provider with user info
class CareProviderWithUser(CareProviderProfile):
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None

# Schema for availability
class AvailabilityBase(BaseModel):
    start_time: datetime = Field(..., description="Availability start time")
    end_time: datetime = Field(..., description="Availability end time")
    is_available: bool = Field(True, description="Whether this slot is available")

class AvailabilityCreate(AvailabilityBase):
    pass

class AvailabilityUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_available: Optional[bool] = None

class Availability(AvailabilityBase):
    id: str
    care_provider_id: str
    created_at: datetime

    class Config:
        from_attributes = True
