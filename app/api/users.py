from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.db.database import get_db
from app.db.models import User
from app.schemas.user import User as UserSchema, UserUpdate, AccountDeletion, EmailUpdate
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserSchema)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user.
    """
    return current_user


@router.put("/me", response_model=UserSchema)
def update_user(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update own user.
    """
    if user_in.password:
        hashed_password = get_password_hash(user_in.password)
        current_user.hashed_password = hashed_password

    if user_in.email:
        current_user.email = user_in.email

    if user_in.name:
        current_user.name = user_in.name

    if user_in.first_name is not None:
        current_user.first_name = user_in.first_name

    if user_in.last_name is not None:
        current_user.last_name = user_in.last_name

    if user_in.display_name is not None:
        current_user.display_name = user_in.display_name

    if user_in.photo_url is not None:
        current_user.photo_url = user_in.photo_url

    if user_in.date_of_birth is not None:
        current_user.date_of_birth = user_in.date_of_birth

    if user_in.country is not None:
        current_user.country = user_in.country

    if user_in.phone_number is not None:
        current_user.phone_number = user_in.phone_number

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserSchema)
def get_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get user by ID. Users can only access their own profile.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


@router.put("/{user_id}", response_model=UserSchema)
def update_user_by_id(
    user_id: str,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update user by ID. Users can only update their own profile.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    if user_in.password:
        hashed_password = get_password_hash(user_in.password)
        current_user.hashed_password = hashed_password

    if user_in.email:
        current_user.email = user_in.email

    if user_in.name:
        current_user.name = user_in.name

    if user_in.first_name is not None:
        current_user.first_name = user_in.first_name

    if user_in.last_name is not None:
        current_user.last_name = user_in.last_name

    if user_in.display_name is not None:
        current_user.display_name = user_in.display_name

    if user_in.photo_url is not None:
        current_user.photo_url = user_in.photo_url

    if user_in.date_of_birth is not None:
        current_user.date_of_birth = user_in.date_of_birth

    if user_in.country is not None:
        current_user.country = user_in.country

    if user_in.phone_number is not None:
        current_user.phone_number = user_in.phone_number

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Deactivate own user account (set is_active to False).
    """
    current_user.is_active = False
    db.add(current_user)
    db.commit()


@router.post("/me/update-email", response_model=UserSchema)
def update_user_email(
    email_data: EmailUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update user email with password verification.
    """
    # Verify password
    if not current_user.hashed_password or not verify_password(email_data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )

    # Check if email is already in use
    existing_user = db.query(User).filter(User.email == email_data.new_email).first()
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already in use by another account"
        )

    # Update email
    current_user.email = email_data.new_email
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user_with_password(
    deletion_data: AccountDeletion,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Deactivate own user account with password verification (set is_active to False).
    """
    # Verify password
    if not current_user.hashed_password or not verify_password(deletion_data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )

    current_user.is_active = False
    db.add(current_user)
    db.commit()
