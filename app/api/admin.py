from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.rbac_deps import require_admin_access, require_manage_all_users
from app.core.auth_middleware import AuthInfo
from app.db.database import get_db
from app.db.models import SpecialistType, User, UserRole
from app.schemas.user import User as UserSchema

router = APIRouter()


class RoleAssignment(BaseModel):
    user_id: str
    role: UserRole
    specialty: SpecialistType = None


class UserRoleUpdate(BaseModel):
    role: UserRole
    specialty: SpecialistType = None


@router.get("/users", response_model=List[UserSchema])
def get_all_users(
    skip: int = 0,
    limit: int = 100,
    auth: AuthInfo = Depends(require_manage_all_users),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all users. Requires 'manage:all-users' scope.
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.put("/users/{user_id}/role", response_model=UserSchema)
def assign_user_role(
    user_id: str,
    role_update: UserRoleUpdate,
    auth: AuthInfo = Depends(require_manage_all_users),
    db: Session = Depends(get_db),
) -> Any:
    """
    Assign role to a user. Requires 'manage:all-users' scope.
    Only admins can assign 'care' role.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update role
    user.role = role_update.role

    # If assigning care role, specialty is required
    if role_update.role == UserRole.CARE:
        if not role_update.specialty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specialty is required when assigning care role"
            )
        user.specialty = role_update.specialty
    else:
        # Clear specialty for non-care roles
        user.specialty = None

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/care-providers", response_model=List[dict])
def get_care_providers_admin(
    specialty: str = None,
    skip: int = 0,
    limit: int = 100,
    auth: AuthInfo = Depends(require_manage_all_users),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all care providers with their details. Requires 'manage:all-users' scope.
    """
    query = db.query(User).filter(User.role == UserRole.CARE, User.is_active == True)

    if specialty:
        try:
            specialty_enum = SpecialistType(specialty.upper())
            query = query.filter(User.specialty == specialty_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid specialty. Must be one of: {[s.value for s in SpecialistType]}"
            )

    care_providers = query.offset(skip).limit(limit).all()

    return [
        {
            "id": provider.id,
            "name": provider.name or f"{provider.first_name or ''} {provider.last_name or ''}".strip(),
            "email": provider.email,
            "specialty": provider.specialty.value if provider.specialty is not None else None,
            "role": provider.role.value,
            "created_at": provider.created_at,
            "is_active": provider.is_active
        }
        for provider in care_providers
    ]


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: str,
    auth: AuthInfo = Depends(require_manage_all_users),
    db: Session = Depends(get_db),
) -> Any:
    """
    Deactivate a user account (set is_active to False). Requires 'manage:all-users' scope.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == auth.sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    user.is_active = False
    db.add(user)
    db.commit()

    return {"message": "User account deactivated successfully"}


@router.put("/users/{user_id}/activate")
def activate_user(
    user_id: str,
    auth: AuthInfo = Depends(require_manage_all_users),
    db: Session = Depends(get_db),
) -> Any:
    """
    Activate a user account (set is_active to True). Requires 'manage:all-users' scope.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = True
    db.add(user)
    db.commit()

    return {"message": "User account activated successfully"}
