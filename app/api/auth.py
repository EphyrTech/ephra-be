import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2 import IntegrityError, sql
from sqlalchemy.orm import Session

from app.core.auth_middleware import AuthInfo, verify_access_token
from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.user import User as UserSchema
from app.services.logto_service import LogtoUserManager
from app.services.user_service import BaseUser

from fastapi.security import OAuth2PasswordBearer
import httpx


logger = logging.getLogger(__name__)
router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"token") 

logto_user_manager = LogtoUserManager()


@router.get("/protected")
async def protected_endpoint(token: str = Depends(oauth2_scheme)) -> Any:
    """
    Example protected endpoint that requires JWT authentication.
    This demonstrates how to protect API endpoints with Logto JWT validation.
    """

    resp = httpx.get(f"{settings.LOGTO_ENDPOINT}/userinfo", headers={"Authorization": f"Bearer {token}"})

    return {"message": "This is a protected endpoint", "auth": token}


@router.get("/me", response_model=UserSchema)
async def get_current_user(
    auth: AuthInfo = Depends(verify_access_token), db: Session = Depends(get_db)
) -> Any:
    """
    Get current user information from JWT token.
    This endpoint validates the JWT token and returns the user information.
    """
        
    user = BaseUser(
            db=db,
            logto_user_manager=logto_user_manager,
            log_to_user_id=auth.sub
        )
    await user.init()

    # application = logto_user.applicationId #TODO: in future identify where he comes from

    await user.upsert_db_user()

    return user.current_db_user


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
