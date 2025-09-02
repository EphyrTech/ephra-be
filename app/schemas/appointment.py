from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    meeting_link: Optional[str] = Field(None, description="Custom meeting link (optional)")
    notes: Optional[str] = Field(None, description="Session notes (optional)")
    reminder_minutes: Optional[int] = Field(15, description="Minutes before appointment to send reminder email")

# Properties to receive via API on update
class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = Field(None, description="Session notes")

# Properties for rescheduling appointments
class AppointmentReschedule(BaseModel):
    start_time: datetime = Field(..., description="New appointment start time")
    end_time: datetime = Field(..., description="New appointment end time")
    reminder_minutes: Optional[int] = Field(15, description="Minutes before appointment to send reminder email")

# Properties to return via API
class Appointment(AppointmentBase):
    id: str
    user_id: str
    status: AppointmentStatus
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Email reminder tracking fields
    email_message_id: Optional[str] = None
    email_scheduled: bool = False
    email_delivered: bool = False
    email_opened: bool = False
    reminder_minutes: int = 15
    # User details for display
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_date_of_birth: Optional[str] = None
    user_country: Optional[str] = None
    care_provider_name: Optional[str] = None
    care_provider_email: Optional[str] = None
    care_provider_first_name: Optional[str] = None
    care_provider_last_name: Optional[str] = None

    class Config:
        from_attributes = True

# Detailed appointment with user and care provider info (kept for backward compatibility)
class AppointmentDetail(Appointment):
    pass
