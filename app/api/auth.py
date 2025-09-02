import logging
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from psycopg2 import IntegrityError, sql
from sqlalchemy.orm import Session

from app.api.deps import create_logto_user_for_existing_user
from app.core.auth_middleware import AuthInfo, verify_access_token
from app.core.config import settings
from app.core.logto_client import get_logto_config
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.auth import (
    GoogleAuth,
    Login,
    LogtoAuthResponse,
    LogtoConfig,
    PasswordReset,
    Token,
)
from app.schemas.user import User as UserSchema
from app.schemas.user import UserCreate
from app.services.logto_service import LogtoService

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


# # LogTo Management API Endpoints


# @router.post("/logto/users", status_code=status.HTTP_201_CREATED)
# async def create_logto_user(
#     user_data: dict, db: Session = Depends(get_db)
# ) -> Any:
#     """
#     Create a new user in LogTo using the Management API.

#     This endpoint allows creating users directly in LogTo with custom data.
#     Requires the user_data to include at least 'primaryEmail'.

#     Example request body:
#     {
#         "primaryEmail": "user@example.com",
#         "password": "SecurePassword123!",
#         "username": "username",
#         "name": "Display Name",
#         "profile": {
#             "givenName": "First",
#             "familyName": "Last"
#         }
#     }
#     """
#     try:
#         logto_service = LogtoService(db=db)
#         created_user = await logto_service.create_logto_user(user_data)

#         if not created_user:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Failed to create user in LogTo"
#             )

#         return {
#             "message": "User created successfully",
#             "user": created_user
#         }
#     except Exception as e:
#         logger.error(f"Error creating LogTo user: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error while creating user"
#         )


# @router.get("/logto/users/{user_id}")
# async def get_logto_user(
#     user_id: str, db: Session = Depends(get_db)
# ) -> Any:
#     """
#     Get user information from LogTo Management API.

#     Args:
#         user_id: LogTo user ID
#     """
#     try:
#         logto_service = LogtoService(db=db)
#         user_data = await logto_service.get_logto_user(user_id)

#         if not user_data:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="User not found in LogTo"
#             )

#         return user_data
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting LogTo user: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error while retrieving user"
#         )


# @router.patch("/logto/users/{user_id}")
# async def update_logto_user(
#     user_id: str, user_data: dict, db: Session = Depends(get_db)
# ) -> Any:
#     """
#     Update user information in LogTo Management API.

#     Args:
#         user_id: LogTo user ID
#         user_data: Dictionary containing fields to update
#     """
#     try:
#         logto_service = LogtoService(db=db)
#         updated_user = await logto_service.update_logto_user(user_id, user_data)

#         if not updated_user:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Failed to update user in LogTo"
#             )

#         return {
#             "message": "User updated successfully",
#             "user": updated_user
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error updating LogTo user: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error while updating user"
#         )


# @router.post("/logto/users/simple", status_code=status.HTTP_201_CREATED)
# async def create_logto_user_simple(
#     email: str,
#     password: Optional[str] = None,
#     username: Optional[str] = None,
#     given_name: Optional[str] = None,
#     family_name: Optional[str] = None,
#     phone: Optional[str] = None,
#     db: Session = Depends(get_db)
# ) -> Any:
#     """
#     Create a LogTo user with a simplified interface using query parameters.

#     This is a convenience endpoint that uses the create_user_with_profile method.

#     Args:
#         email: User's email address (required)
#         password: Plain text password (optional)
#         username: Username (optional)
#         given_name: First name (optional)
#         family_name: Last name (optional)
#         phone: Phone number (optional)
#     """
#     try:
#         logto_service = LogtoService(db=db)

#         # Build display name from given_name and family_name
#         name = None
#         if given_name and family_name:
#             name = f"{given_name} {family_name}"
#         elif given_name:
#             name = given_name
#         elif family_name:
#             name = family_name

#         created_user = await logto_service.create_user_with_profile(
#             email=email,
#             password=password,
#             username=username,
#             phone=phone,
#             name=name,
#             given_name=given_name,
#             family_name=family_name
#         )

#         if not created_user:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Failed to create user in LogTo"
#             )

#         return {
#             "message": "User created successfully",
#             "user": created_user
#         }
#     except Exception as e:
#         logger.error(f"Error creating LogTo user: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error while creating user"
#         )


# @router.post("/logto/sync-user/{user_id}", status_code=status.HTTP_200_OK)
# async def sync_local_user_to_logto(
#     user_id: str, db: Session = Depends(get_db)
# ) -> Any:
#     """
#     Create a LogTo user for an existing local user.

#     This endpoint is useful when you have a user in your local database
#     but they don't exist in LogTo yet. It will create the LogTo user
#     and link them to the local user.

#     Args:
#         user_id: Local user ID
#     """
#     try:
#         # Find the local user
#         user = db.query(User).filter(User.id == user_id).first()
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="User not found"
#             )

#         # Check if user already has a LogTo ID
#         if user.logto_user_id:
#             return {
#                 "message": "User already has LogTo ID",
#                 "logto_user_id": user.logto_user_id,
#                 "user_id": user.id
#             }

#         # Create LogTo user
#         success = await create_logto_user_for_existing_user(user, db)

#         if success:
#             return {
#                 "message": "Successfully created LogTo user and linked to local user",
#                 "logto_user_id": user.logto_user_id,
#                 "user_id": user.id
#             }
#         else:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Failed to create LogTo user"
#             )

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error syncing user to LogTo: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error while syncing user"
#         )


# @router.post("/logto/sync-user-by-email", status_code=status.HTTP_200_OK)
# async def sync_local_user_to_logto_by_email(
#     email: str, db: Session = Depends(get_db)
# ) -> Any:
#     """
#     Create a LogTo user for an existing local user by email.

#     Args:
#         email: User's email address
#     """
#     try:
#         # Find the local user by email
#         user = db.query(User).filter(User.email == email).first()
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="User not found"
#             )

#         # Check if user already has a LogTo ID
#         if user.logto_user_id:
#             return {
#                 "message": "User already has LogTo ID",
#                 "logto_user_id": user.logto_user_id,
#                 "user_id": user.id,
#                 "email": user.email
#             }

#         # Create LogTo user
#         success = await create_logto_user_for_existing_user(user, db)

#         if success:
#             return {
#                 "message": "Successfully created LogTo user and linked to local user",
#                 "logto_user_id": user.logto_user_id,
#                 "user_id": user.id,
#                 "email": user.email
#             }
#         else:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Failed to create LogTo user"
#             )

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error syncing user to LogTo by email: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error while syncing user"
#         )
#     except Exception as e:
#         logger.error(f"Failed to get current user: {e}")
#         db.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to get user information",
#         )
