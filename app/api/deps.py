import logging
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth_middleware import AuthInfo, verify_access_token
from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.auth import TokenPayload

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


def get_current_user_from_auth(
    auth: AuthInfo = Depends(verify_access_token), db: Session = Depends(get_db)
) -> User:
    """
    Get current user from AuthInfo (Logto JWT token).
    This function bridges the gap between verify_access_token (returns AuthInfo)
    and endpoints that need User objects.
    """
    try:
        # Find user by Logto subject ID
        user = db.query(User).filter(User.logto_user_id == auth.sub).first()

        if not user:
            # Auto-create user if they don't exist (following the pattern from auth.py)
            logger.info(f"Creating new user for Logto ID: {auth.sub}")

            # Extract user information from AuthInfo
            email = auth.email
            name = auth.name or auth.given_name

            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is required but not provided in token",
                )

            user = User(
                email=email,
                logto_user_id=auth.sub,
                role=UserRole.USER,
                hashed_password=None,  # No password for Logto users
                name=name,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user with ID: {user.id}")

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )

        return user

    except Exception as e:
        logger.error(f"Error getting user from auth: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information",
        )
