from datetime import timedelta
from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from psycopg2 import sql, IntegrityError

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.logto_client import get_logto_config
from app.core.auth_middleware import verify_access_token, AuthInfo
from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.auth import (
    Token,
    Login,
    GoogleAuth,
    PasswordReset,
    LogtoAuthResponse,
    LogtoConfig,
)
from app.schemas.user import UserCreate, User as UserSchema

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED
)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> Any:
    """
    Register a new user.
    """
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )

    db_user = User(
        email=user_in.email,
        name=user_in.name,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        display_name=user_in.display_name,
        photo_url=user_in.photo_url,
        date_of_birth=user_in.date_of_birth,
        country=user_in.country,
        phone_number=user_in.phone_number,
        hashed_password=get_password_hash(user_in.password),
        role=UserRole.USER,  # Default role for new users
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=Token)
def login(login_data: Login, db: Session = Depends(get_db)) -> Any:
    """
    Login with email and password to get an access token.
    """
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            subject=user.id, expires_delta=access_token_expires, role=user.role.value
        ),
        "token_type": "bearer",
    }


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Any:
    """
    OAuth2 compatible token login for Swagger UI authorization.
    Use this endpoint for the "Authorize" button in Swagger UI.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            subject=user.id, expires_delta=access_token_expires, role=user.role.value
        ),
        "token_type": "bearer",
    }


@router.post("/google", response_model=Token)
def google_auth(google_data: GoogleAuth, db: Session = Depends(get_db)) -> Any:
    """
    Authenticate with Google.
    """
    # In a real implementation, you would verify the Google token
    # and extract user information from it

    # For now, we'll just return a mock token
    return {
        "access_token": "mock_google_token",
        "token_type": "bearer",
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(reset_data: PasswordReset, db: Session = Depends(get_db)) -> Any:
    """
    Password recovery.
    """
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        # Don't reveal that the user doesn't exist
        return {"message": "Password reset email sent"}

    # In a real implementation, you would send an email with a reset link

    return {"message": "Password reset email sent"}


# Logto Authentication Endpoints


@router.get("/logto/config", response_model=LogtoConfig)
def get_logto_configuration() -> Any:
    """
    Get Logto configuration for frontend.
    """
    return get_logto_config()


@router.get("/protected")
async def protected_endpoint(auth: AuthInfo = Depends(verify_access_token)) -> Any:
    """
    Example protected endpoint that requires JWT authentication.
    This demonstrates how to protect API endpoints with Logto JWT validation.
    """
    return {"message": "This is a protected endpoint", "user": auth.to_dict()}


@router.get("/me", response_model=UserSchema)
async def get_current_user(
    auth: AuthInfo = Depends(verify_access_token), db: Session = Depends(get_db)
) -> Any:
    """
    Get current user information from JWT token.
    This endpoint validates the JWT token and returns the user information.
    """
    try:
        # Find user by Logto subject ID
        user = db.query(User).filter(User.logto_user_id == auth.sub).first()

        if not user:
            # If user doesn't exist, create a new one
            # Extract user info from JWT payload if available

            # Debug: Log all available claims from Logto JWT
            logger.info(
                f"Creating new user from Logto JWT. Available claims: {vars(auth)}"
            )

            raw_email = getattr(auth, "email", None)
            logger.info(f"Raw email from Logto: {raw_email}")

            # Handle Logto .local domain emails in development
            if raw_email and raw_email.endswith("@logto.local"):
                # Convert .local emails to valid domain
                username = raw_email.split("@")[0]
                email = f"{username}@ephyrtech.com"
                logger.info(f"Converted .local email: {raw_email} -> {email}")
            elif raw_email:
                email = raw_email
                logger.info(f"Using provided email: {email}")
            else:
                # Fallback email if none provided
                email = f"user_{auth.sub}@ephyrtech.com"
                logger.warning(f"No email provided by Logto, using fallback: {email}")

            name = (
                getattr(auth, "name", None)
                or getattr(auth, "given_name", None)
                or "NoName Persona"
            )
            logger.info(f"User name from Logto: {name}")

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

        return user
    except IntegrityError as e:
        logger.error(f"Integrity error while creating user: {e}")
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information",
        )
    except Exception as e:
        logger.error(f"Failed to get current user: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information",
        )
