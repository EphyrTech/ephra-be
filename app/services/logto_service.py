"""
Logto authentication service for user management and synchronization.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

import httpx
from logto import LogtoClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import User, UserRole
from app.schemas.auth import LogtoUserInfo



logger = logging.getLogger(__name__)



# Address Model
class Address(BaseModel):
    formatted: str
    streetAddress: str
    locality: str
    region: str
    postalCode: str
    country: str

# Profile Model
class Profile(BaseModel):
    familyName: str
    givenName: str
    middleName: Optional[str]
    nickname: Optional[str]
    preferredUsername: Optional[str]
    profile: Optional[str]
    website: Optional[str]
    gender: Optional[str]
    birthdate: Optional[str]
    zoneinfo: Optional[str]
    locale: Optional[str]
    address: Address

# Base User Model
class UserBase(BaseModel):
    username: Optional[str] = None
    primaryEmail: str
    primaryPhone: Optional[str] = None
    name: str
    avatar: Optional[str] = None
    customData: Optional[Dict[str, Any]] = Field(default_factory=dict)
    profile: Optional[Profile] = None

# Request Model for Creating a User
class UserCreateRequest(UserBase):
    password: Optional[str] = None
    passwordDigest: Optional[str] = None
    passwordAlgorithm: Optional[str] = Field(default="Argon2i")

# Response Model for Creating a User
class UserCreateResponse(UserBase):
    id: str
    identities: Dict[str, Dict[str, Any]]  # A map for additional properties
    lastSignInAt: float
    createdAt: float
    updatedAt: float
    applicationId: str
    isSuspended: bool
    hasPassword: bool
    ssoIdentities: List[Dict[str, Any]]  # List to hold SSO identity details

# Request Model for Updating a User
class UserUpdateRequest(UserBase):
    pass  # Inherits from UserBase, so we leverage its fields

# Response Model for Updating a User
class UserUpdateResponse(UserCreateResponse):
    pass  # Inherits from UserCreateResponse since it has same structure

# Response Model for Getting a User
class UserGetResponse(UserCreateResponse):
    pass  # Inherits from UserCreateResponse since it has the same structure


class LogtoService:
    """Service for handling Logto authentication and user synchronization."""

    def __init__(self, db: Session, logto_client: LogtoClient = None):
        self.db = db
        self.logto_client = logto_client
        self._management_token = None
        self._token_expires_at = None

        # Extract tenant ID from endpoint for Management API
        if settings.LOGTO_ENDPOINT:
            self.tenant_id = self._extract_tenant_id(settings.LOGTO_ENDPOINT)
            self.management_api_base = f"https://{self.tenant_id}.ephyrtech.com/api"
        else:
            self.tenant_id = None
            self.management_api_base = None

    def _extract_tenant_id(self, endpoint: str) -> str:
        """Extract tenant ID from LogTo endpoint URL."""
        # Handle URLs like https://logto-wkc0gogw84o0g4owkswswc80.ephyrtech.com/
        # or https://tenant-id.logto.app/
        if ".logto.app" in endpoint:
            # Extract from tenant-id.logto.app format
            return endpoint.split("//")[1].split(".logto.app")[0]
        else:
            # For custom domains, extract the subdomain part
            # This assumes the format like logto-{tenant_id}.domain.com
            domain_part = endpoint.split("//")[1].split("/")[0]
            if "logto-" in domain_part:
                return domain_part.split("logto-")[1].split(".")[0]
            else:
                # Fallback: use the whole subdomain
                return domain_part.split(".")[0]

    async def _get_management_token(self) -> Optional[str]:
        """Get access token for LogTo Management API using client credentials."""
        try:
            # Check if we have a valid token
            if (self._management_token and self._token_expires_at and
                datetime.now() < self._token_expires_at - timedelta(minutes=5)):
                return self._management_token

            if not all([settings.LOGTO_ENDPOINT, settings.LOGTO_MANAGEMENT_APP_ID, settings.LOGTO_MANAGEMENT_APP_SECRET]):
                logger.error("LogTo configuration missing for Management API")
                return None

            # Prepare token request
            endpoint = settings.LOGTO_ENDPOINT.rstrip('/')
            token_url = f"{endpoint}/oidc/token"
            resource = f"{endpoint}/api" # for selfhosted logto

            data = {
                "grant_type": "client_credentials",
                "client_id": settings.LOGTO_MANAGEMENT_APP_ID,
                "client_secret": settings.LOGTO_MANAGEMENT_APP_SECRET,
                "resource": resource,
                "scope": "all"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    data=data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                )

                if response.status_code == 200:
                    token_data = response.json()
                    self._management_token = token_data["access_token"]
                    expires_in = token_data.get("expires_in", 3600)
                    self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                    logger.info("Successfully obtained LogTo Management API token")
                    return self._management_token
                else:
                    logger.error(f"Failed to get Management API token: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error getting Management API token: {e}")
            return None

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
        
    async def create_logto_user(self, user_data: UserCreateRequest) -> Optional[UserCreateResponse]:
        """
        Create a new user in LogTo using the Management API.

        Args:
            user_data: Dictionary containing user information with keys like:
                - primaryEmail (str): User's primary email
                - primaryPhone (str, optional): User's primary phone
                - username (str, optional): Username
                - password (str, optional): Plain text password
                - name (str, optional): Display name
                - avatar (str, optional): Avatar URL
                - customData (dict, optional): Custom user data
                - profile (dict, optional): User profile information

        Returns:
            Dictionary containing the created user data or None if failed
        """
        try:
            token = await self._get_management_token()
            if not token:
                logger.error("Failed to get Management API token for user creation")
                return None

            if not self.management_api_base:
                logger.error("Management API base URL not configured")
                return None

            # Prepare the request
            url = f"{self.management_api_base}/users"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Validate required fields
            if not user_data.primaryEmail:
                logger.error("primaryEmail is required for user creation")
                return None

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=user_data.model_dump(), headers=headers)

                if response.status_code == 201:
                    created_user = UserCreateResponse.model_validate(response.json())
                    logger.info(f"Successfully created LogTo user: {created_user.id}")
                    return created_user
                else:
                    logger.error(f"Failed to create LogTo user: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error creating LogTo user: {e}")
            return None

    async def get_logto_user(self, user_id: str) -> Optional[UserGetResponse]:
        """
        Get user information from LogTo Management API.

        Args:
            user_id: LogTo user ID

        Returns:
            Dictionary containing user data or None if not found
        """
        try:
            token = await self._get_management_token()
            if not token:
                logger.error("Failed to get Management API token for user retrieval")
                return None

            if not self.management_api_base:
                logger.error("Management API base URL not configured")
                return None

            url = f"{self.management_api_base}/users"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(headers=headers) as client:
                response = await client.get("https://logto-t40coowscs4c40okgs8gso0k.ephyrtech.com/api/users?page=1&page_size=20")

                if response.status_code == 200:
                    user_data = UserGetResponse.model_validate(response.json())
                    logger.info(f"Successfully retrieved LogTo user: {user_id}")
                    return user_data
                elif response.status_code == 404:
                    logger.warning(f"LogTo user not found: {user_id}")
                    return None
                else:
                    logger.error(f"Failed to get LogTo user: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error getting LogTo user: {e}")
            return None

    async def update_logto_user(self, user_id: str, user_data: UserUpdateRequest) -> Optional[UserUpdateResponse]:
        """
        Update user information in LogTo Management API.

        Args:
            user_id: LogTo user ID
            user_data: Dictionary containing fields to update

        Returns:
            Dictionary containing updated user data or None if failed
        """
        try:
            token = await self._get_management_token()
            if not token:
                logger.error("Failed to get Management API token for user update")
                return None

            if not self.management_api_base:
                logger.error("Management API base URL not configured")
                return None

            url = f"{self.management_api_base}/users/{user_id}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.patch(url, json=user_data.model_dump(), headers=headers)

                if response.status_code == 200:
                    updated_user = UserUpdateResponse.model_validate(response.json())
                    logger.info(f"Successfully updated LogTo user: {user_id}")
                    return updated_user
                else:
                    logger.error(f"Failed to update LogTo user: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error updating LogTo user: {e}")
            return None

    async def create_user_with_profile(
        self,
        email: str,
        password: Optional[str] = None,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        avatar: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Convenience method to create a LogTo user with common profile fields.

        Args:
            email: User's email address (required)
            password: Plain text password (optional)
            username: Username (optional)
            phone: Phone number (optional)
            name: Display name (optional)
            given_name: First name (optional)
            family_name: Last name (optional)
            avatar: Avatar URL (optional)
            custom_data: Additional custom data (optional)

        Returns:
            Dictionary containing the created user data or None if failed
        """
        user_data = UserCreateRequest(
            primaryEmail=email,
            password=password,
            username=username,
            primaryPhone=phone,
            name=name,
            avatar=avatar,
            customData=custom_data,
            passwordDigest=None,
        )

        # Build profile object if any profile fields are provided
        profile = Profile(
            givenName=given_name,
            familyName=family_name,
            middleName=None,
            nickname=None,
            preferredUsername=None,
            profile=None,
            website=None,
            gender=None,
            birthdate=None,
            zoneinfo=None,
            locale=None,
            address=None
        )


        if given_name:
            profile["givenName"] = given_name
        if family_name:
            profile["familyName"] = family_name

        if profile:
            user_data["profile"] = profile

        return await self.create_logto_user(user_data)

    async def sync_local_user_to_logto(self, user: User) -> Optional[str]:
        """
        Create a LogTo user for an existing local user and update the local user with LogTo ID.

        Args:
            user: The local User object

        Returns:
            LogTo user ID if successful, None if failed
        """
        try:
            # Check if user already has LogTo ID
            if user.logto_user_id:
                logger.info(f"User {user.id} already has LogTo ID: {user.logto_user_id}")
                return user.logto_user_id

            # Prepare user data for LogTo
            user_data: Dict[str, Any] = {
                "primaryEmail": user.email,
            }

            # Add name if available
            if user.display_name:
                user_data["name"] = user.display_name
            elif user.name:
                user_data["name"] = user.name
            elif user.first_name or user.last_name:
                first_name = str(user.first_name) if user.first_name else ""
                last_name = str(user.last_name) if user.last_name else ""
                user_data["name"] = f"{first_name} {last_name}".strip()

            # Add profile information if available
            profile: Dict[str, str] = {}
            if user.first_name:
                profile["givenName"] = str(user.first_name)
            if user.last_name:
                profile["familyName"] = str(user.last_name)
            if profile:
                user_data["profile"] = profile

            # Add optional fields
            if user.phone_number:
                user_data["primaryPhone"] = user.phone_number
            if user.photo_url:
                user_data["avatar"] = user.photo_url

            # Add custom data with local user info
            user_data["customData"] = {
                "localUserId": user.id,
                "createdFromLocal": True,
                "role": user.role.value if user.role else "USER"
            }

            # Create user in LogTo
            created_user = await self.create_logto_user(user_data)

            if created_user:
                # Update local user with LogTo ID
                user.logto_user_id = created_user["id"]
                self.db.commit()
                logger.info(f"Successfully synced local user {user.id} to LogTo user {created_user['id']}")
                return created_user["id"]
            else:
                logger.error(f"Failed to create LogTo user for local user {user.id}")
                return None

        except Exception as e:
            logger.error(f"Error syncing local user {user.id} to LogTo: {e}")
            return None

