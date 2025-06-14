from datetime import timedelta
from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.logto_client import create_logto_client, get_logto_config
from app.services.logto_service import LogtoService
from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.auth import Token, Login, GoogleAuth, PasswordReset, LogtoAuthResponse, LogtoConfig
from app.schemas.user import UserCreate, User as UserSchema

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
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
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Any:
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


@router.get("/logto/sign-in")
async def logto_sign_in(request: Request, response: Response) -> Any:
    """
    Initiate Logto sign-in process.
    """
    logger.info("Initiating Logto sign-in process")

    client = create_logto_client(request, response)
    if not client:
        logger.error("Logto client not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logto authentication is not configured"
        )

    try:
        logger.info("Creating sign-in URL")
        sign_in_url = await client.signIn(
            redirectUri=settings.LOGTO_REDIRECT_URI,
        )
        logger.info(f"Sign-in URL created: {sign_in_url}")

        # Create the redirect response
        redirect_response = RedirectResponse(url=sign_in_url)

        # Ensure any session cookies set by the client are included in the response
        # The create_logto_client should have set session data via the storage
        logger.info("Returning redirect response with session cookies")
        return redirect_response

    except Exception as e:
        logger.error(f"Failed to initiate sign-in: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate sign-in: {str(e)}"
        )


@router.get("/logto/sign-up")
async def logto_sign_up(request: Request, response: Response) -> Any:
    """
    Initiate Logto sign-up process.
    """
    client = create_logto_client(request, response)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logto authentication is not configured"
        )

    try:
        sign_in_url = await client.signIn(
            redirectUri=settings.LOGTO_REDIRECT_URI,
            interactionMode="signUp",
        )
        return RedirectResponse(url=sign_in_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate sign-up: {str(e)}"
        )


@router.get("/logto/callback")
async def logto_callback(request: Request, response: Response, db: Session = Depends(get_db)) -> Any:
    """
    Handle Logto authentication callback and redirect to frontend.
    """
    logger.info(f"Logto callback received: {request.url}")

    client = create_logto_client(request, response)
    if not client:
        logger.error("Logto client not configured")
        # Redirect to frontend with error
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error=logto_not_configured")

    try:
        # Log the current session state for debugging
        logger.info(f"Request cookies: {request.cookies}")

        # Handle the sign-in callback
        logger.info("Handling sign-in callback...")
        await client.handleSignInCallback(str(request.url))

        # Check if client is authenticated after callback
        if not client.isAuthenticated():
            logger.error("Client not authenticated after callback")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error=authentication_failed")

        # Create Logto service and authenticate user
        logger.info("Creating Logto service and authenticating user...")
        logto_service = LogtoService(db, client)
        auth_result = await logto_service.authenticate_user()

        if not auth_result:
            logger.error("Failed to authenticate user with Logto service")
            # Redirect to frontend with error
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error=authentication_failed")

        user, access_token = auth_result
        logger.info(f"User authenticated successfully: {user.email}")

        # Redirect to frontend with success and token
        # The frontend can extract the token from the URL and store it
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?token={access_token}&user_id={user.id}")

    except Exception as e:
        logger.error(f"Logto callback error: {e}", exc_info=True)
        # Redirect to frontend with error
        error_message = str(e).replace(' ', '_').replace(':', '').replace('-', '_')
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error={error_message}")


@router.get("/logto/sign-out")
async def logto_sign_out(request: Request, response: Response) -> Any:
    """
    Initiate Logto sign-out process.
    """
    client = create_logto_client(request, response)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logto authentication is not configured"
        )

    try:
        sign_out_url = await client.signOut(
            postLogoutRedirectUri=settings.LOGTO_POST_LOGOUT_REDIRECT_URI
        )
        return RedirectResponse(url=sign_out_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate sign-out: {str(e)}"
        )


@router.get("/logto/user", response_model=UserSchema)
async def get_logto_user(request: Request, response: Response, db: Session = Depends(get_db)) -> Any:
    """
    Get current user information from Logto session.
    """
    client = create_logto_client(request, response)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logto authentication is not configured"
        )

    try:
        if not client.isAuthenticated():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        logto_service = LogtoService(db, client)
        auth_result = await logto_service.authenticate_user()

        if not auth_result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )

        user, _ = auth_result
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )
