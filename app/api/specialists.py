from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Specialist, Availability, User
from app.schemas.specialist import (
    Specialist as SpecialistSchema,
    SpecialistWithAvailability,
    Availability as AvailabilitySchema,
)
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[SpecialistSchema])
def get_specialists(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Retrieve specialists.
    """
    specialists = db.query(Specialist).offset(skip).limit(limit).all()
    return specialists

@router.get("/{specialist_id}", response_model=SpecialistSchema)
def get_specialist(
    specialist_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific specialist by id.
    """
    specialist = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not specialist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specialist not found",
        )
    return specialist

@router.get("/{specialist_id}/availability", response_model=List[AvailabilitySchema])
def get_specialist_availability(
    specialist_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specialist's availability.
    """
    specialist = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not specialist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specialist not found",
        )
    
    availabilities = db.query(Availability).filter(
        Availability.specialist_id == specialist_id
    ).all()
    
    return availabilities
