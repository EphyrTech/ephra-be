from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Shared properties
class JournalBase(BaseModel):
    title: str
    content: Optional[str] = None

# Properties to receive via API on creation
class JournalCreate(JournalBase):
    pass

# Properties to receive via API on update
class JournalUpdate(JournalBase):
    title: Optional[str] = None

# Properties to return via API
class Journal(JournalBase):
    id: str
    user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True
