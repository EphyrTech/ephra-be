"""API endpoints for care provider management"""

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, UserRole, CareProviderProfile, Availability
from app.schemas.care_provider import (
    CareProviderProfile as CareProviderProfileSchema,
    CareProviderProfileCreate,
    CareProviderProfileUpdate,
    CareProviderWithUser,
    Availability as AvailabilitySchema,
    AvailabilityCreate,
    AvailabilityUpdate,
)
from app.api.deps import get_current_user
from app.api.role_deps import require_care_or_admin
from app.services.exceptions import ServiceException

router = APIRouter()


@router.get("/", response_model=List[CareProviderWithUser])
def get_care_providers(
    specialty: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get list of care providers, optionally filtered by specialty.
    """
    query = db.query(CareProviderProfile).join(User).filter(
        User.is_active == True,
        CareProviderProfile.is_accepting_patients == True
    )

    if specialty:
        from app.db.models import SpecialistType
        try:
            specialty_enum = SpecialistType(specialty.lower())
            query = query.filter(CareProviderProfile.specialty == specialty_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid specialty. Must be one of: {[s.value for s in SpecialistType]}"
            )

    profiles = query.offset(skip).limit(limit).all()

    # Convert to response format with user info
    result = []
    for profile in profiles:
        profile_dict = {
            **profile.__dict__,
            "user_name": profile.user.name,
            "user_email": profile.user.email,
            "user_first_name": profile.user.first_name,
            "user_last_name": profile.user.last_name,
        }
        result.append(profile_dict)

    return result


@router.get("/me", response_model=CareProviderProfileSchema)
def get_my_profile(
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get current care provider's profile.
    """
    if current_user.role != UserRole.CARE_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only care providers can access this endpoint"
        )

    profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider profile not found"
        )

    return profile


@router.post("/me", response_model=CareProviderProfileSchema, status_code=status.HTTP_201_CREATED)
def create_my_profile(
    profile_in: CareProviderProfileCreate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create care provider profile for current user.
    """
    if current_user.role != UserRole.CARE_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only care providers can create profiles"
        )

    # Check if profile already exists
    existing_profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == current_user.id
    ).first()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Care provider profile already exists"
        )

    # Create profile
    profile_data = profile_in.model_dump()
    profile = CareProviderProfile(user_id=current_user.id, **profile_data)

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


@router.put("/me", response_model=CareProviderProfileSchema)
def update_my_profile(
    profile_in: CareProviderProfileUpdate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update current care provider's profile.
    """
    if current_user.role != UserRole.CARE_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only care providers can update profiles"
        )

    profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider profile not found"
        )

    # Update profile
    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return profile


@router.get("/{care_provider_id}", response_model=CareProviderWithUser)
def get_care_provider(
    care_provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get a specific care provider by ID.
    """
    profile = db.query(CareProviderProfile).join(User).filter(
        CareProviderProfile.user_id == care_provider_id,
        User.is_active == True
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider not found"
        )

    return {
        **profile.__dict__,
        "user_name": profile.user.name,
        "user_email": profile.user.email,
        "user_first_name": profile.user.first_name,
        "user_last_name": profile.user.last_name,
    }


# Availability management endpoints

@router.get("/me/availability", response_model=List[AvailabilitySchema])
def get_my_availability(
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get current care provider's availability slots.
    """
    if current_user.role != UserRole.CARE_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only care providers can access this endpoint"
        )

    # Get care provider profile
    profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider profile not found"
        )

    # Get availability slots
    availabilities = db.query(Availability).filter(
        Availability.care_provider_id == profile.id
    ).order_by(Availability.start_time).all()

    return availabilities


@router.post("/me/availability", response_model=AvailabilitySchema, status_code=status.HTTP_201_CREATED)
def create_my_availability(
    availability_in: AvailabilityCreate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new availability slot for current care provider.
    """
    if current_user.role != UserRole.CARE_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only care providers can create availability"
        )

    # Get care provider profile
    profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider profile not found"
        )

    # Validate time range
    if availability_in.start_time >= availability_in.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )

    # Check for overlapping availability slots
    overlapping = db.query(Availability).filter(
        Availability.care_provider_id == profile.id,
        Availability.start_time < availability_in.end_time,
        Availability.end_time > availability_in.start_time
    ).first()

    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This time slot overlaps with an existing availability slot"
        )

    # Create availability slot
    availability_data = availability_in.model_dump()
    availability = Availability(care_provider_id=profile.id, **availability_data)

    db.add(availability)
    db.commit()
    db.refresh(availability)

    return availability


@router.put("/me/availability/{availability_id}", response_model=AvailabilitySchema)
def update_my_availability(
    availability_id: str,
    availability_in: AvailabilityUpdate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update an availability slot for current care provider.
    """
    if current_user.role != UserRole.CARE_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only care providers can update availability"
        )

    # Get care provider profile
    profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider profile not found"
        )

    # Get availability slot
    availability = db.query(Availability).filter(
        Availability.id == availability_id,
        Availability.care_provider_id == profile.id
    ).first()

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )

    # Update availability
    update_data = availability_in.model_dump(exclude_unset=True)

    # Validate time range if both times are being updated
    start_time = update_data.get('start_time', availability.start_time)
    end_time = update_data.get('end_time', availability.end_time)

    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )

    # Check for overlapping availability slots (excluding current one)
    if 'start_time' in update_data or 'end_time' in update_data:
        overlapping = db.query(Availability).filter(
            Availability.care_provider_id == profile.id,
            Availability.id != availability_id,
            Availability.start_time < end_time,
            Availability.end_time > start_time
        ).first()

        if overlapping:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This time slot overlaps with an existing availability slot"
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(availability, field, value)

    db.commit()
    db.refresh(availability)

    return availability


@router.delete("/me/availability/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_availability(
    availability_id: str,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete an availability slot for current care provider.
    """
    if current_user.role != UserRole.CARE_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only care providers can delete availability"
        )

    # Get care provider profile
    profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider profile not found"
        )

    # Get availability slot
    availability = db.query(Availability).filter(
        Availability.id == availability_id,
        Availability.care_provider_id == profile.id
    ).first()

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )

    # Check if there are any appointments scheduled during this time
    from app.db.models import Appointment, AppointmentStatus

    conflicting_appointments = db.query(Appointment).filter(
        Appointment.care_provider_id == current_user.id,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
        Appointment.start_time < availability.end_time,
        Appointment.end_time > availability.start_time
    ).first()

    if conflicting_appointments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete availability slot with scheduled appointments"
        )

    # Delete availability slot
    db.delete(availability)
    db.commit()
