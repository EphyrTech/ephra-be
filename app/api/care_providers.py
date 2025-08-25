"""API endpoints for care provider management"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_from_auth
from app.api.role_deps import require_care_or_admin
from app.db.database import get_db
from app.db.models import SpecialistType, User
from app.schemas.care_provider import Availability as AvailabilitySchema
from app.schemas.care_provider import AvailabilityCreate, AvailabilityUpdate
from app.schemas.care_provider import CareProviderProfile as CareProviderProfileSchema
from app.schemas.care_provider import (
    CareProviderProfileCreate,
    CareProviderProfileUpdate,
    CareProviderWithUser,
)
from app.services.care_provider_service import CareProviderService
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionError,
    ServiceException,
    ValidationError,
)

router = APIRouter()


def handle_service_exception(e: ServiceException) -> HTTPException:
    """Convert service exceptions to HTTP exceptions"""
    if isinstance(e, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    elif isinstance(e, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    elif isinstance(e, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    elif isinstance(e, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    elif isinstance(e, BusinessRuleError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        )
    else:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get("/", response_model=List[CareProviderWithUser])
def get_care_providers(
    specialty: Optional[str] = Query(
        None, description="Filter by specialty: mental or physical"
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_auth),
) -> Any:
    """
    Get list of care providers, optionally filtered by specialty.
    """
    try:
        service = CareProviderService(db)
        return service.get_care_providers(specialty, skip, limit)
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get("/me", response_model=CareProviderProfileSchema)
def get_my_profile(
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get current care provider's profile.
    """
    try:
        service = CareProviderService(db)
        return service.get_my_profile(current_user)
    except ServiceException as e:
        raise handle_service_exception(e)


@router.post(
    "/me", response_model=CareProviderProfileSchema, status_code=status.HTTP_201_CREATED
)
def create_my_profile(
    profile_in: CareProviderProfileCreate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create care provider profile for current user.
    """
    try:
        service = CareProviderService(db)
        return service.create_my_profile(profile_in, current_user)
    except ServiceException as e:
        raise handle_service_exception(e)


@router.put("/me", response_model=CareProviderProfileSchema)
def update_my_profile(
    profile_in: CareProviderProfileUpdate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update current care provider's profile.
    """
    try:
        service = CareProviderService(db)
        return service.update_my_profile(profile_in, current_user)
    except ServiceException as e:
        raise handle_service_exception(e)


@router.get("/{care_provider_id}", response_model=CareProviderWithUser)
def get_care_provider(
    care_provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_auth),
) -> Any:
    """
    Get a specific care provider by ID.
    """
    try:
        service = CareProviderService(db)
        return service.get_care_provider_by_id(care_provider_id)
    except ServiceException as e:
        raise handle_service_exception(e)


# Availability management endpoints


@router.get("/me/availability", response_model=List[AvailabilitySchema])
def get_my_availability(
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get current care provider's availability slots.
    """
    try:
        service = CareProviderService(db)
        return service.get_my_availability(current_user)
    except ServiceException as e:
        raise handle_service_exception(e)


@router.post(
    "/me/availability",
    response_model=AvailabilitySchema,
    status_code=status.HTTP_201_CREATED,
)
def create_my_availability(
    availability_in: AvailabilityCreate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new availability slot for current care provider.
    """
    try:
        service = CareProviderService(db)
        return service.create_my_availability(availability_in, current_user)
    except ServiceException as e:
        raise handle_service_exception(e)


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
    try:
        service = CareProviderService(db)
        return service.update_my_availability(
            availability_id, availability_in, current_user
        )
    except ServiceException as e:
        raise handle_service_exception(e)


@router.delete(
    "/me/availability/{availability_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_my_availability(
    availability_id: str,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete an availability slot for current care provider.
    """
    try:
        service = CareProviderService(db)
        service.delete_my_availability(availability_id, current_user)
    except ServiceException as e:
        raise handle_service_exception(e)
