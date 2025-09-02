import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


def generate_uuid():
    return str(uuid.uuid4())

class UserRole(str, enum.Enum):
    USER = "user"
    CARE_PROVIDER = "care_provider"  # Renamed for clarity
    ADMIN = "admin"

class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class SpecialistType(str, enum.Enum):
    MENTAL = "mental"  # Keep existing values for compatibility
    PHYSICAL = "physical"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    display_name = Column(String)
    photo_url = Column(String)
    date_of_birth = Column(Date)
    country = Column(String)
    phone_number = Column(String)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth users
    logto_user_id = Column(String, unique=True, nullable=True, index=True)  # Logto user ID
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    journals = relationship("Journal", back_populates="user", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="user", foreign_keys="Appointment.user_id", cascade="all, delete-orphan")
    care_provider_profile = relationship("CareProviderProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    provided_appointments = relationship("Appointment", foreign_keys="Appointment.care_provider_id")
    media_files = relationship("MediaFile", back_populates="user", cascade="all, delete-orphan")


class CareProviderProfile(Base):
    """Separate profile for care providers with their professional information"""
    __tablename__ = "care_provider_profiles"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    specialty = Column(Enum(SpecialistType), nullable=False)
    bio = Column(Text)
    hourly_rate = Column(Integer)  # In cents
    license_number = Column(String)
    years_experience = Column(Integer)
    education = Column(Text)
    certifications = Column(Text)
    is_accepting_patients = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="care_provider_profile")
    availabilities = relationship("Availability", back_populates="care_provider", cascade="all, delete-orphan")

class Journal(Base):
    __tablename__ = "journals"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text)

    # Enhanced journaling fields
    mood = Column(String)  # Main mood: 'rad', 'good', 'meh', 'bad', 'awful'
    emotions = Column(JSON)  # Array of detailed emotions
    sleep = Column(String)  # Sleep quality: 'excellent', 'good', 'okay', 'poor', 'terrible'
    quick_note = Column(Text)  # Short note for quick thoughts
    notes = Column(Text)  # Detailed notes
    date = Column(DateTime(timezone=True))  # Entry date (can be different from created_at)
    shared_with_coach = Column(Boolean, default=False)

    # Media URLs (stored as JSON arrays)
    photo_urls = Column(JSON)  # Array of photo URLs
    voice_memo_urls = Column(JSON)  # Array of voice memo URLs
    voice_memo_durations = Column(JSON)  # Array of durations in seconds
    pdf_urls = Column(JSON)  # Array of PDF URLs
    pdf_names = Column(JSON)  # Array of PDF names

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="journals")

class Availability(Base):
    __tablename__ = "availabilities"

    id = Column(String, primary_key=True, default=generate_uuid)
    care_provider_id = Column(String, ForeignKey("care_provider_profiles.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    is_available = Column(Boolean, default=True)  # Can be marked as unavailable
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    care_provider = relationship("CareProviderProfile", back_populates="availabilities")

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    care_provider_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Care provider user ID
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    meeting_link = Column(String)
    notes = Column(Text)  # Session notes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Email reminder tracking fields
    email_message_id = Column(String, nullable=True)  # Mailgun message ID for tracking
    email_scheduled = Column(Boolean, default=False)  # Boolean indicating if reminder email was scheduled
    email_delivered = Column(Boolean, default=False)  # Boolean tracking if email was delivered
    email_opened = Column(Boolean, default=False)  # Boolean tracking if email was opened
    reminder_minutes = Column(Integer, default=15)  # Configurable reminder time in minutes

    # Relationships
    user = relationship("User", back_populates="appointments", foreign_keys=[user_id])
    care_provider = relationship("User", foreign_keys=[care_provider_id], overlaps="provided_appointments")

class UserAssignment(Base):
    """Assignment relationship between users and care providers"""
    __tablename__ = "user_assignments"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    care_provider_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Admin who made the assignment
    is_active = Column(Boolean, default=True)
    notes = Column(Text)  # Optional notes about the assignment

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    care_provider = relationship("User", foreign_keys=[care_provider_id])
    assigner = relationship("User", foreign_keys=[assigned_by])

    # Ensure unique assignment per user-care provider pair
    __table_args__ = (
        UniqueConstraint('user_id', 'care_provider_id', name='unique_user_care_provider_assignment'),
    )


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(Integer)  # In bytes
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="media_files")


class PersonalJournal(Base):
    """Personal journal entries created by care providers and admins for patients"""
    __tablename__ = "personal_journals"

    id = Column(String, primary_key=True, default=generate_uuid)
    patient_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Entry datetime (when the entry is for)
    entry_datetime = Column(DateTime(timezone=True), nullable=False)

    # Content
    title = Column(String, nullable=False)
    content = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Sharing settings
    is_shared = Column(Boolean, default=False)  # Whether this entry can be shared with other care providers
    shared_with_care_providers = Column(JSON)  # Array of care provider IDs who can view this entry

    # Relationships
    patient = relationship("User", foreign_keys=[patient_id])
    author = relationship("User", foreign_keys=[author_id])
    attachments = relationship("PersonalJournalAttachment", back_populates="journal", cascade="all, delete-orphan")


class PersonalJournalAttachment(Base):
    """Attachments for personal journal entries (files, voice recordings, URLs)"""
    __tablename__ = "personal_journal_attachments"

    id = Column(String, primary_key=True, default=generate_uuid)
    journal_id = Column(String, ForeignKey("personal_journals.id", ondelete="CASCADE"), nullable=False)

    # Attachment type and data
    attachment_type = Column(String, nullable=False)  # 'file', 'voice', 'url'

    # For files and voice recordings
    file_path = Column(String)  # Path to uploaded file
    filename = Column(String)  # Original filename
    file_type = Column(String)  # MIME type
    file_size = Column(Integer)  # File size in bytes

    # For voice recordings
    duration_seconds = Column(Integer)  # Duration of voice recording
    transcription = Column(Text)  # Transcribed text from voice recording

    # For URLs
    url = Column(String)  # URL link
    url_title = Column(String)  # Optional title for the URL
    url_description = Column(Text)  # Optional description for the URL

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal = relationship("PersonalJournal", back_populates="attachments")
