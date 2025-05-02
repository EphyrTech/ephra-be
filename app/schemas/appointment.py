from pydantic import BaseModel
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
    specialist_id: str
    start_time: datetime
    end_time: datetime

# Properties to receive via API on creation
class AppointmentCreate(AppointmentBase):
    pass

# Properties to receive via API on update
class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None

# Properties to return via API
class Appointment(AppointmentBase):
    id: str
    user_id: str
    status: AppointmentStatus
    meeting_link: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
