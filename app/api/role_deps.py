from typing import List
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, UserRole
from app.core.auth_middleware import verify_access_token


def require_roles(allowed_roles: List[UserRole]):
    """
    Dependency factory that creates a dependency function to check if the current user has one of the allowed roles.
    """

    def role_checker(current_user: User = Depends(verify_access_token)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}",
            )
        return current_user

    return role_checker


def require_admin(current_user: User = Depends(verify_access_token)) -> User:
    """
    Dependency to ensure the current user is an admin.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


def require_care_or_admin(current_user: User = Depends(verify_access_token)) -> User:
    """
    Dependency to ensure the current user is either care provider or admin.
    """
    if current_user.role not in [UserRole.CARE_PROVIDER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Care provider or admin access required",
        )
    return current_user


def get_care_providers(
    specialty: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_access_token),
) -> List[User]:
    """
    Get list of care providers, optionally filtered by specialty.
    Only accessible by admin or care providers.
    """
    if current_user.role not in [UserRole.CARE_PROVIDER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Care provider or admin access required.",
        )

    # Get care providers (users with care_provider role and active care provider profiles)
    query = db.query(User).filter(
        User.role == UserRole.CARE_PROVIDER, User.is_active == True
    )

    if specialty:
        from app.db.models import SpecialistType, CareProviderProfile

        try:
            specialty_enum = SpecialistType(specialty.upper())
            query = query.join(CareProviderProfile).filter(
                CareProviderProfile.specialty == specialty_enum
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid specialty. Must be one of: {[s.value for s in SpecialistType]}",
            )

    return query.all()
