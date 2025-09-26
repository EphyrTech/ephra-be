import logging
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session
import pendulum

from app.core.auth_middleware import AuthInfo, verify_access_token
from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.auth import TokenPayload
from app.services import logto_service
from app.services.logto_service import (
    LogtoManagerService,
    UserCreateRequest,
    UserUpdateRequest,
    UserGetResponse
)

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


async def create_logto_user_for_existing_user(user: User, db: Session) -> bool:
    """
    Create a LogTo user for an existing local user.
    This is useful when you have a user in your local database but they don't exist in LogTo yet.

    Args:
        user: The local User object
        db: Database session

    Returns:
        bool: True if LogTo user was created successfully, False otherwise
    """
    try:
        logto_service = LogtoService(db=db)

        logto_user = UserCreateRequest(
            primaryEmail=user.email,
            name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        )

        # Add custom data with local user info
        logto_user.customData = {
            "localUserId": user.id,
            "createdFromLocal": True,
            "syncedAt": pendulum.now().to_iso8601_string()
        }

        # Create user in LogTo
        created_user = await logto_service.create_logto_user(logto_user)

        if created_user:
            # Update local user with LogTo ID
            user.logto_user_id = created_user.id
            db.commit()
            logger.info(f"Successfully created LogTo user {created_user.id} for local user {user.id}")
            return True
        else:
            logger.error(f"Failed to create LogTo user for local user {user.id}")
            return False

    except Exception as e:
        logger.error(f"Error creating LogTo user for existing user {user.id}: {e}")
        return False


async def get_current_user_from_auth(
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
