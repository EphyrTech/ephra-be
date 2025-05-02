from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MediaFileBase(BaseModel):
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None  # In bytes

class MediaFileCreate(MediaFileBase):
    file_path: str

class MediaFile(MediaFileBase):
    id: str
    user_id: str
    file_path: str
    created_at: datetime
    
    class Config:
        from_attributes = True
