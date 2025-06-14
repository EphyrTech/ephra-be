"""Schemas for user-care provider assignments"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# Base schema
class UserAssignmentBase(BaseModel):
    user_id: str = Field(..., description="ID of the user to be assigned")
    care_provider_id: str = Field(..., description="ID of the care provider")
    notes: Optional[str] = Field(None, description="Optional notes about the assignment")


# Schema for creating assignment
class UserAssignmentCreate(UserAssignmentBase):
    pass


# Schema for updating assignment
class UserAssignmentUpdate(BaseModel):
    is_active: Optional[bool] = Field(None, description="Whether the assignment is active")
    notes: Optional[str] = Field(None, description="Optional notes about the assignment")


# Schema for returning assignment
class UserAssignment(UserAssignmentBase):
    id: str
    assigned_at: datetime
    assigned_by: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# Schema for assignment with user details
class UserAssignmentWithDetails(UserAssignment):
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_country: Optional[str] = None
    care_provider_name: Optional[str] = None
    care_provider_email: Optional[str] = None
    care_provider_first_name: Optional[str] = None
    care_provider_last_name: Optional[str] = None
    assigner_name: Optional[str] = None


# Schema for bulk assignment operations
class BulkUserAssignmentCreate(BaseModel):
    user_ids: list[str] = Field(..., description="List of user IDs to assign")
    care_provider_id: str = Field(..., description="ID of the care provider")
    notes: Optional[str] = Field(None, description="Optional notes about the assignments")


# Schema for assignment statistics
class AssignmentStats(BaseModel):
    total_assignments: int
    active_assignments: int
    inactive_assignments: int
    users_assigned: int
    care_providers_with_assignments: int
