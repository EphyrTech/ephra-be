from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class AppointmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

# Shared properties
class AppointmentBase(BaseModel):
    care_provider_id: str = Field(..., description="ID of the care provider")
    start_time: datetime = Field(..., description="Appointment start time")
    end_time: datetime = Field(..., description="Appointment end time")

# Properties to receive via API on creation
class AppointmentCreate(AppointmentBase):
    user_id: Optional[str] = Field(None, description="User ID (required for care providers and admins)")

# Properties to receive via API on update
class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = Field(None, description="Session notes")

# Properties to return via API
class Appointment(AppointmentBase):
    id: str
    user_id: str
    status: AppointmentStatus
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # User details for display
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    care_provider_name: Optional[str] = None
    care_provider_email: Optional[str] = None

    class Config:
        from_attributes = True

# Detailed appointment with user and care provider info
class AppointmentDetail(Appointment):
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    care_provider_name: Optional[str] = None
    care_provider_email: Optional[str] = None
