from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime
from enum import Enum

class SpecialistType(str, Enum):
    MENTAL = "mental"
    PHYSICAL = "physical"

# Shared properties
class SpecialistBase(BaseModel):
    name: str
    email: str
    specialist_type: SpecialistType
    bio: Optional[str] = None
    hourly_rate: int  # In cents

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        # Import here to avoid circular imports
        from app.schemas.user import validate_email_field
        return validate_email_field(v)

# Properties to return via API
class Specialist(SpecialistBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Availability
class AvailabilityBase(BaseModel):
    start_time: datetime
    end_time: datetime

class AvailabilityCreate(AvailabilityBase):
    specialist_id: str

class Availability(AvailabilityBase):
    id: str
    specialist_id: str
    
    class Config:
        from_attributes = True

# Specialist with availability
class SpecialistWithAvailability(Specialist):
    availabilities: List[Availability] = []
