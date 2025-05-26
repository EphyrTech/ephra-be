from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# Shared properties
class JournalBase(BaseModel):
    title: str
    content: Optional[str] = None
    mood: Optional[str] = None
    emotions: Optional[List[str]] = None
    sleep: Optional[str] = None
    quick_note: Optional[str] = None
    notes: Optional[str] = None
    date: Optional[datetime] = None
    shared_with_coach: Optional[bool] = False
    photo_urls: Optional[List[str]] = None
    voice_memo_urls: Optional[List[str]] = None
    voice_memo_durations: Optional[List[int]] = None
    pdf_urls: Optional[List[str]] = None
    pdf_names: Optional[List[str]] = None

# Properties to receive via API on creation
class JournalCreate(JournalBase):
    pass

# Properties to receive via API on update
class JournalUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    mood: Optional[str] = None
    emotions: Optional[List[str]] = None
    sleep: Optional[str] = None
    quick_note: Optional[str] = None
    notes: Optional[str] = None
    date: Optional[datetime] = None
    shared_with_coach: Optional[bool] = None
    photo_urls: Optional[List[str]] = None
    voice_memo_urls: Optional[List[str]] = None
    voice_memo_durations: Optional[List[int]] = None
    pdf_urls: Optional[List[str]] = None
    pdf_names: Optional[List[str]] = None

# Properties to return via API
class Journal(JournalBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
