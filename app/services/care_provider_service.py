"""Care provider service for business logic"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Appointment,
    AppointmentStatus,
    Availability,
    CareProviderProfile,
    SpecialistType,
    User,
    UserRole,
)
from app.schemas.care_provider import (
    AvailabilityCreate,
    AvailabilityUpdate,
    CareProviderProfileCreate,
    CareProviderProfileUpdate,
    CareProviderWithUser,
)
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class CareProviderService:
    """Service for care provider-related business logic"""

    def __init__(self, db: Session):
        self.db = db

    def get_care_providers(
        self, specialty: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get list of care providers with proper filtering and eager loading"""
        logger.info(
            "Fetching care providers",
            extra={"specialty": specialty, "skip": skip, "limit": limit},
        )

        # Validate pagination
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 1000:
            raise ValidationError("Limit must be between 1 and 1000")

        # Build query with eager loading to prevent N+1 queries
        query = (
            self.db.query(CareProviderProfile)
            .join(User)
            .options(joinedload(CareProviderProfile.user))
            .filter(
                User.is_active == True,
                CareProviderProfile.is_accepting_patients == True,
            )
        )

        # Apply specialty filter if provided
        if specialty:
            try:
                specialty_enum = SpecialistType(specialty.lower())
                query = query.filter(CareProviderProfile.specialty == specialty_enum)
            except ValueError:
                raise ValidationError(
                    f"Invalid specialty. Must be one of: {[s.value for s in SpecialistType]}"
                )

        profiles = query.offset(skip).limit(limit).all()

        logger.info(
            f"Found {len(profiles)} care providers", extra={"count": len(profiles)}
        )

        # Transform to response format
        return [self._transform_profile_with_user(profile) for profile in profiles]

    def get_care_provider_by_id(self, care_provider_id: str) -> Dict[str, Any]:
        """Get a specific care provider by user ID"""
        profile = (
            self.db.query(CareProviderProfile)
            .join(User)
            .options(joinedload(CareProviderProfile.user))
            .filter(
                CareProviderProfile.user_id == care_provider_id, User.is_active == True
            )
            .first()
        )

        if not profile:
            raise NotFoundError("Care provider not found")

        return self._transform_profile_with_user(profile)

    def get_my_profile(self, current_user: User) -> CareProviderProfile:
        """Get current care provider's profile"""
        self._ensure_care_provider_role(current_user)

        profile = (
            self.db.query(CareProviderProfile)
            .filter(CareProviderProfile.user_id == current_user.id)
            .first()
        )

        if not profile:
            raise NotFoundError("Care provider profile not found")

        return profile

    def create_my_profile(
        self, profile_data: CareProviderProfileCreate, current_user: User
    ) -> CareProviderProfile:
        """Create care provider profile for current user"""
        self._ensure_care_provider_role(current_user)

        # Check if profile already exists
        existing_profile = (
            self.db.query(CareProviderProfile)
            .filter(CareProviderProfile.user_id == current_user.id)
            .first()
        )

        if existing_profile:
            raise ConflictError("Care provider profile already exists")

        # Create profile
        profile = CareProviderProfile(
            user_id=current_user.id, **profile_data.model_dump()
        )

        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)

        return profile

    def update_my_profile(
        self, profile_data: CareProviderProfileUpdate, current_user: User
    ) -> CareProviderProfile:
        """Update current care provider's profile"""
        profile = self.get_my_profile(current_user)

        # Apply updates
        update_data = profile_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)

        self.db.commit()
        self.db.refresh(profile)

        return profile

    def get_my_availability(self, current_user: User) -> List[Availability]:
        """Get current care provider's availability slots"""
        profile = self.get_my_profile(current_user)

        # Optimized query with proper ordering and filtering
        availabilities = (
            self.db.query(Availability)
            .filter(Availability.care_provider_id == str(profile.id))
            .order_by(Availability.start_time)
            .all()
        )

        return availabilities

    def create_my_availability(
        self, availability_data: AvailabilityCreate, current_user: User
    ) -> Availability:
        """Create a new availability slot for current care provider"""
        profile = self.get_my_profile(current_user)

        # Validate time range
        if availability_data.start_time >= availability_data.end_time:
            raise ValidationError("Start time must be before end time")

        # Check for overlapping availability slots
        overlapping = self._check_availability_overlap(
            str(profile.id), availability_data.start_time, availability_data.end_time
        )

        if overlapping:
            raise ConflictError(
                "This time slot overlaps with an existing availability slot"
            )

        # Create availability slot
        availability = Availability(
            care_provider_id=profile.id, **availability_data.model_dump()
        )

        self.db.add(availability)
        self.db.commit()
        self.db.refresh(availability)

        return availability

    def update_my_availability(
        self,
        availability_id: str,
        availability_data: AvailabilityUpdate,
        current_user: User,
    ) -> Availability:
        """Update an availability slot for current care provider"""
        profile = self.get_my_profile(current_user)
        availability = self._get_availability_by_id(availability_id, str(profile.id))

        update_data = availability_data.model_dump(exclude_unset=True)

        # Validate time range if being updated
        start_time = update_data.get("start_time", availability.start_time)
        end_time = update_data.get("end_time", availability.end_time)

        if start_time >= end_time:
            raise ValidationError("Start time must be before end time")

        # Check for overlapping availability slots (excluding current one)
        if "start_time" in update_data or "end_time" in update_data:
            overlapping = self._check_availability_overlap(
                str(profile.id), start_time, end_time, exclude_id=availability_id
            )

            if overlapping:
                raise ConflictError(
                    "This time slot overlaps with an existing availability slot"
                )

        # Apply updates
        for field, value in update_data.items():
            setattr(availability, field, value)

        self.db.commit()
        self.db.refresh(availability)

        return availability

    def delete_my_availability(self, availability_id: str, current_user: User) -> None:
        """Delete an availability slot for current care provider"""
        profile = self.get_my_profile(current_user)
        availability = self._get_availability_by_id(availability_id, str(profile.id))

        # Check if there are any appointments scheduled during this time
        conflicting_appointments = (
            self.db.query(Appointment)
            .filter(
                Appointment.care_provider_id == current_user.id,
                Appointment.status.in_(
                    [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
                ),
                Appointment.start_time < availability.end_time,
                Appointment.end_time > availability.start_time,
            )
            .first()
        )

        if conflicting_appointments:
            raise BusinessRuleError(
                "Cannot delete availability slot with scheduled appointments"
            )

        # Delete availability slot
        self.db.delete(availability)
        self.db.commit()

    # Private helper methods

    def _ensure_care_provider_role(self, user: User) -> None:
        """Ensure user has care provider role"""
        if user.role != UserRole.CARE_PROVIDER:
            raise PermissionError("Only care providers can access this resource")

    def _transform_profile_with_user(
        self, profile: CareProviderProfile
    ) -> Dict[str, Any]:
        """Transform profile to include user information"""
        return {
            **profile.__dict__,
            "user_name": profile.user.name,
            "user_email": profile.user.email,
            "user_first_name": profile.user.first_name,
            "user_last_name": profile.user.last_name,
        }

    def _check_availability_overlap(
        self,
        care_provider_id: str,
        start_time: datetime,
        end_time: datetime,
        exclude_id: Optional[str] = None,
    ) -> bool:
        """Check if availability slot overlaps with existing ones"""
        try:
            query = self.db.query(Availability).filter(
                Availability.care_provider_id == care_provider_id,
                Availability.start_time < end_time,
                Availability.end_time > start_time,
            )

            if exclude_id:
                query = query.filter(Availability.id != exclude_id)

            return query.first() is not None
        except Exception as e:
            raise ValidationError(f"Error checking availability overlap: {str(e)}")

    def _get_availability_by_id(
        self, availability_id: str, care_provider_id: str
    ) -> Availability:
        """Get availability slot by ID and ensure it belongs to the care provider"""
        availability = (
            self.db.query(Availability)
            .filter(
                Availability.id == availability_id,
                Availability.care_provider_id == care_provider_id,
            )
            .first()
        )

        if not availability:
            raise NotFoundError("Availability slot not found")

        return availability
