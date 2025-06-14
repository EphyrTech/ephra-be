"""Schemas for personal journal entries created by care providers and admins"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AttachmentType(str, Enum):
    FILE = "file"
    VOICE = "voice"
    URL = "url"


# Personal Journal Attachment Schemas
class PersonalJournalAttachmentBase(BaseModel):
    attachment_type: AttachmentType
    
    # For files and voice recordings
    file_path: Optional[str] = None
    filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    
    # For voice recordings
    duration_seconds: Optional[int] = None
    transcription: Optional[str] = None
    
    # For URLs
    url: Optional[str] = None
    url_title: Optional[str] = None
    url_description: Optional[str] = None


class PersonalJournalAttachmentCreate(PersonalJournalAttachmentBase):
    pass


class PersonalJournalAttachmentUpdate(BaseModel):
    attachment_type: Optional[AttachmentType] = None
    file_path: Optional[str] = None
    filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[int] = None
    transcription: Optional[str] = None
    url: Optional[str] = None
    url_title: Optional[str] = None
    url_description: Optional[str] = None


class PersonalJournalAttachment(PersonalJournalAttachmentBase):
    id: str
    journal_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Personal Journal Schemas
class PersonalJournalBase(BaseModel):
    patient_id: str = Field(..., description="ID of the patient this entry is about")
    entry_datetime: datetime = Field(..., description="Date and time this entry is for")
    title: str = Field(..., min_length=1, max_length=255, description="Title of the journal entry")
    content: Optional[str] = Field(None, description="Main content of the journal entry")
    is_shared: Optional[bool] = Field(False, description="Whether this entry can be shared with other care providers")
    shared_with_care_providers: Optional[List[str]] = Field(None, description="List of care provider IDs who can view this entry")


class PersonalJournalCreate(PersonalJournalBase):
    attachments: Optional[List[PersonalJournalAttachmentCreate]] = Field(None, description="List of attachments for this entry")


class PersonalJournalUpdate(BaseModel):
    entry_datetime: Optional[datetime] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    is_shared: Optional[bool] = None
    shared_with_care_providers: Optional[List[str]] = None


class PersonalJournal(PersonalJournalBase):
    id: str
    author_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    attachments: List[PersonalJournalAttachment] = []
    
    class Config:
        from_attributes = True


class PersonalJournalWithDetails(PersonalJournal):
    """Personal journal with additional patient and author details"""
    patient_name: Optional[str] = None
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    patient_email: Optional[str] = None
    patient_country: Optional[str] = None
    author_name: Optional[str] = None
    author_first_name: Optional[str] = None
    author_last_name: Optional[str] = None
    author_email: Optional[str] = None


# Voice transcription request
class VoiceTranscriptionRequest(BaseModel):
    file_path: str = Field(..., description="Path to the voice file to transcribe")
    language: Optional[str] = Field("en", description="Language code for transcription")


class VoiceTranscriptionResponse(BaseModel):
    transcription: str = Field(..., description="Transcribed text from the voice file")
    confidence: Optional[float] = Field(None, description="Confidence score of the transcription")
    duration_seconds: Optional[int] = Field(None, description="Duration of the audio file in seconds")


# Bulk operations
class PersonalJournalBulkCreate(BaseModel):
    patient_ids: List[str] = Field(..., description="List of patient IDs to create entries for")
    entry_datetime: datetime = Field(..., description="Date and time this entry is for")
    title: str = Field(..., min_length=1, max_length=255, description="Title of the journal entry")
    content: Optional[str] = Field(None, description="Main content of the journal entry")
    is_shared: Optional[bool] = Field(False, description="Whether this entry can be shared with other care providers")


# Statistics and reporting
class PersonalJournalStats(BaseModel):
    total_entries: int
    entries_this_week: int
    entries_this_month: int
    total_patients_with_entries: int
    most_active_author: Optional[str] = None
    most_documented_patient: Optional[str] = None
