from sqlalchemy import Boolean, Column, DateTime, Date, ForeignKey, Integer, String, Text, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

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

    # Relationships
    user = relationship("User", back_populates="appointments", foreign_keys=[user_id])
    care_provider = relationship("User", foreign_keys=[care_provider_id], overlaps="provided_appointments")

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
