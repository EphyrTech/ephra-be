from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import CareProviderProfile, Availability, User, UserRole, SpecialistType
from app.schemas.care_provider import (
    CareProviderWithUser,
    Availability as AvailabilitySchema,
)
from app.api.deps import get_current_user
from app.api.role_deps import require_care_or_admin

router = APIRouter()

@router.get("/care-providers", response_model=List[CareProviderWithUser])
def get_care_providers_endpoint(
    specialty: Optional[str] = Query(None, description="Filter by specialty: mental or physical"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve care providers, optionally filtered by specialty.
    """
    query = db.query(CareProviderProfile).join(User).filter(
        User.role == UserRole.CARE_PROVIDER,
        User.is_active == True,
        CareProviderProfile.is_accepting_patients == True
    )

    if specialty:
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

@router.get("/{care_provider_id}", response_model=CareProviderWithUser)
def get_care_provider(
    care_provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get a specific care provider by user ID.
    """
    profile = db.query(CareProviderProfile).join(User).filter(
        CareProviderProfile.user_id == care_provider_id,
        User.is_active == True
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider not found",
        )

    return {
        **profile.__dict__,
        "user_name": profile.user.name,
        "user_email": profile.user.email,
        "user_first_name": profile.user.first_name,
        "user_last_name": profile.user.last_name,
    }

@router.get("/{care_provider_id}/availability", response_model=List[AvailabilitySchema])
def get_care_provider_availability(
    care_provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get a care provider's availability.
    """
    # Get the care provider profile
    profile = db.query(CareProviderProfile).filter(
        CareProviderProfile.user_id == care_provider_id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider not found",
        )

    availabilities = db.query(Availability).filter(
        Availability.care_provider_id == profile.id,
        Availability.is_available == True
    ).all()

    return availabilities
