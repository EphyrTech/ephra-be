"""
Logto authentication service for user management and synchronization.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from logto import LogtoClient
from logto.models.response import UserInfoResponse
import logging

from app.db.models import User, UserRole
from app.schemas.auth import LogtoUserInfo
from app.core.security import create_access_token
from datetime import timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class LogtoService:
    """Service for handling Logto authentication and user synchronization."""
    
    def __init__(self, db: Session, logto_client: LogtoClient):
        self.db = db
        self.logto_client = logto_client
    
    async def get_user_info(self) -> Optional[LogtoUserInfo]:
        """Get user information from Logto."""
        try:
            if not self.logto_client.isAuthenticated():
                return None
            
            user_info = await self.logto_client.fetchUserInfo()
            if not user_info:
                return None
            
            return LogtoUserInfo(
                sub=user_info.sub,
                email=getattr(user_info, 'email', None),
                name=getattr(user_info, 'name', None),
                given_name=getattr(user_info, 'given_name', None),
                family_name=getattr(user_info, 'family_name', None),
                picture=getattr(user_info, 'picture', None),
                phone_number=getattr(user_info, 'phone_number', None),
            )
        except Exception as e:
            logger.error(f"Failed to get user info from Logto: {e}")
            return None
    
    def find_user_by_logto_id(self, logto_user_id: str) -> Optional[User]:
        """Find user by Logto user ID."""
        return self.db.query(User).filter(User.logto_user_id == logto_user_id).first()
    
    def find_user_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def create_or_update_user(self, logto_user_info: LogtoUserInfo) -> User:
        """Create or update user from Logto user information."""
        # First try to find by Logto ID
        user = self.find_user_by_logto_id(logto_user_info.sub)
        
        # If not found by Logto ID, try to find by email
        if not user and logto_user_info.email:
            user = self.find_user_by_email(logto_user_info.email)
            if user:
                # Link existing user to Logto
                user.logto_user_id = logto_user_info.sub
        
        # Create new user if not found
        if not user:
            user = User(
                email=logto_user_info.email or f"user_{logto_user_info.sub}@logto.local",
                logto_user_id=logto_user_info.sub,
                role=UserRole.USER,
                hashed_password=None,  # No password for Logto users
            )
            self.db.add(user)
        
        # Update user information from Logto
        self._update_user_from_logto(user, logto_user_info)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def _update_user_from_logto(self, user: User, logto_user_info: LogtoUserInfo) -> None:
        """Update user fields from Logto user information."""
        if logto_user_info.email:
            user.email = logto_user_info.email
        
        if logto_user_info.name:
            user.name = logto_user_info.name
        
        if logto_user_info.given_name:
            user.first_name = logto_user_info.given_name
        
        if logto_user_info.family_name:
            user.last_name = logto_user_info.family_name
        
        if logto_user_info.picture:
            user.photo_url = logto_user_info.picture
        
        if logto_user_info.phone_number:
            user.phone_number = logto_user_info.phone_number
        
        # Set display name if not already set
        if not user.display_name:
            if user.first_name and user.last_name:
                user.display_name = f"{user.first_name} {user.last_name}"
            elif user.name:
                user.display_name = user.name
            elif user.first_name:
                user.display_name = user.first_name
    
    def create_access_token_for_user(self, user: User) -> str:
        """Create JWT access token for user."""
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return create_access_token(
            subject=user.id,
            expires_delta=access_token_expires,
            role=user.role.value
        )
    
    async def authenticate_user(self) -> Optional[tuple[User, str]]:
        """
        Authenticate user with Logto and return user and access token.
        Returns None if authentication fails.
        """
        try:
            # Get user info from Logto
            logto_user_info = await self.get_user_info()
            if not logto_user_info:
                return None
            
            # Create or update user
            user = self.create_or_update_user(logto_user_info)
            
            # Create access token
            access_token = self.create_access_token_for_user(user)
            
            return user, access_token
        except Exception as e:
            logger.error(f"Failed to authenticate user with Logto: {e}")
            return None
