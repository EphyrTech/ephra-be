"""
Logto authentication service for user management and synchronization.
"""

from csv import Error
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, TypeVar, Type
from pydantic import BaseModel, Field

import httpx
from logto import LogtoClient, LogtoConfig

from app.core.config import settings

from enum import Enum


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
    profile: Optional[Dict[str, Any]] = None

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
    ssoIdentities: Optional[List[Dict[str, Any]]] = None  # List to hold SSO identity details

# Request Model for Updating a User
class UserUpdateRequest(UserBase):
    pass  # Inherits from UserBase, so we leverage its fields

# Response Model for Updating a User
class UserUpdateResponse(UserCreateResponse):
    pass  # Inherits from UserCreateResponse since it has same structure

# Response Model for Getting a User
class UserGetResponse(UserCreateResponse):
    pass  # Inherits from UserCreateResponse since it has the same structure


class LogtoUserRole(BaseModel):
    tenantId: str
    id: str
    name: str
    description: Optional[str] = None
    type: str
    isDefault: bool



class AccountFieldEnum(Enum):
        OFF = "Off"
        READ_ONLY = "ReadOnly"
        EDIT = "Edit"

    
class AccountDataFields(BaseModel):
        name: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        avatar: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        profile: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        email: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        phone: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        password: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        username: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        social: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        customData: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)
        mfa: Optional[AccountFieldEnum] = Field(default=AccountFieldEnum.EDIT)

    
class AccountData(BaseModel):
        enabled: Optional[bool] = Field(default=True)
        fields: AccountDataFields
        webauthnRelatedOrigins: Optional[List] = Field(default=[]) 



ResponseModel = TypeVar('ResponseModel', bound=BaseModel)

class LogtoManagerService:
    """Service for handling Logto authentication and user synchronization."""

    _http_client: httpx.AsyncClient

    def __init__(self):
        self.logto_client = self.init_client()
        self._management_token = None
        self._token_expires_at = None
        self.management_api_base = f"{settings.LOGTO_ENDPOINT}"

        self._http_client = httpx.AsyncClient(base_url=self.management_api_base, timeout=30)

    async def close(self):
        await self._http_client.aclose()


    async def _make_management_request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        response_model: Optional[Type[ResponseModel]] = None,
        success_status: int = 200,
        error_message_prefix: str = "Request to Management API failed"
    ) -> Optional[ResponseModel]:
        """
        Internal helper using the persistent HTTP client.
        """
        try:
            # 1. Get Token
            token = await self._get_management_token()
            if not token:
                logger.error(f"{error_message_prefix}: Failed to get Management API token")
                return None

            # 2. Build Headers (Dynamic, as the token changes)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # 3. Execute Request using the persistent self._client
            # Note: We now use self._client directly, no 'async with' block around it.
            # The base_url is set in __init__, so we only use the relative 'path'.
            
            request_func = getattr(self._http_client, method.lower())
            
            if method in ['GET', 'DELETE']:
                response = await request_func(
                    path, 
                    headers=headers
                )
            else:
                response = await request_func(
                    path, 
                    json=json_data, 
                    headers=headers
                )

            # 4. Handle Response (Error and Validation logic remain the same)
            if response.status_code == success_status:
                if response_model:
                    try:
                        result = response_model.model_validate(response.json())
                        # Path uses base_url from client setup, response.url is full URL after execution
                        logger.info(f"Successfully executed {method} request to {response.url}")
                        return result
                    except Exception as validation_e:
                        logger.error(f"Failed to validate response model for {path}: {validation_e}")
                        return None
                elif success_status == 204:
                    return True
                else:
                    return response.json() 
            else:
                logger.error(
                    f"{error_message_prefix} ({method} {path}): "
                    f"{response.status_code} - {response.text}"
                )
                return None

        except httpx.HTTPError as he:
            logger.error(f"HTTP Error during {method} {path}: {he}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during {method} {path}: {e}")
            return None


    @staticmethod
    def init_client(logto_config: Optional[LogtoConfig] = None):
        """_summary_
        Args:
            logto_config (Optional[LogtoConfig], optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """

        if not logto_config:
            logto_config = LogtoConfig(
                endpoint=settings.LOGTO_ENDPOINT,
                appId=settings.LOGTO_APP_ID,
                appSecret=settings.LOGTO_APP_SECRET,
            )
        
        return LogtoClient(logto_config)
    
    async def _get_management_token(self) -> Optional[str]:
        """Get access token for LogTo Management API using client credentials."""
        try:
            # Check if we have a valid token
            if (self._management_token and self._token_expires_at and
                datetime.now() < self._token_expires_at - timedelta(minutes=5)):
                return self._management_token

            if not all([settings.LOGTO_ENDPOINT, settings.LOGTO_APP_ID, settings.LOGTO_APP_SECRET]):
                logger.error("LogTo configuration missing for Management API")
                return None

            # Prepare token request
            token_url = f"{self.management_api_base}/oidc/token"

            data = {
                "grant_type": "client_credentials",
                "client_id": settings.LOGTO_APP_ID,
                "client_secret": settings.LOGTO_APP_SECRET,
                "resource": "https://default.logto.app/api",
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
            
    async def update_account_center_settings(self, account_data):
        path = "/api/account-center"
        return await self._make_management_request(
            method="PATCH",
            path=path,
            json_data=user_data.model_dump(by_alias=True, exclude_none=True),
            response_model=UserUpdateResponse,
            success_status=200,
            error_message_prefix=f"Failed to update logTo user {user_id}"
        )




class LogtoUserManager(LogtoManagerService):
        
    async def get(self, user_id):
        """Get user data for the given ID.

        Args:
            user_id (str): The unique identifier of the user.

        Returns:
            UserGetResponse: User data for the given ID.
        """
        path = f"/api/users/{user_id}"
        return await self._make_management_request(
            method="GET",
            path=path,
            response_model=UserGetResponse,
            success_status=200,
            error_message_prefix=f"Failed to get logTo user {user_id}"
        )
    
    async def update(self, user_id, user_data: UserUpdateRequest) -> UserUpdateResponse|None:
        path = f"/api/users/{user_id}"
        return await self._make_management_request(
            method="PATCH",
            path=path,
            json_data=user_data.model_dump(by_alias=True, exclude_none=True),
            response_model=UserUpdateResponse,
            success_status=200,
            error_message_prefix=f"Failed to update logTo user {user_id}"
        )

    async def create(self, user_data: UserCreateRequest) -> UserCreateResponse|None:
        path = f"/api/users"
        return await self._make_management_request(
            method="POST",
            path=path,
            json_data=user_data.model_dump(by_alias=True, exclude_none=True),
            response_model=UserCreateResponse,
            success_status=200,
            error_message_prefix=f"Failed to create logTo user {user_data.primaryEmail}"
        )
    
    async def delete(self, user_id: str):
        path = f"/api/users/{user_id}"
        return await self._make_management_request(
            method="DELETE",
            path=path,
            success_status=204,
            error_message_prefix=f"Failed to delete logTo user {user_id}"
        )
    
    async def get_roles(self, user_id):
        path = f"/api/users/{user_id}/roles"
        resp = await self._make_management_request(
            method="GET",
            path=path,
            success_status=200,
            error_message_prefix=f"Failed to get logTo user roles {user_id}"
        )
        
        roles = [LogtoUserRole.model_validate(r) for r in resp] if resp else None

        return roles
    
    async def update_roles(self, user_id: str, role_ids: List[str]):
        """Update API resource roles assigned to the user. This will replace the existing roles.

        Args:
            user_id (str): The unique identifier of the user.
            role_ids (List[str]): An array of API resource role IDs to assign.

        Raises:
            Error: Minimum length of each role is 1.

        """
        if len(role_ids) < 1:
            raise Error("Not enough roles specified for {user_id}")
        path = f"/api/users/{user_id}"
        return await self._make_management_request(
            method="PUT",
            path=path,
            json_data={
                "roleIds": role_ids
            },
            success_status=200,
            error_message_prefix=f"Failed to update logTo user roles {user_id}"
        )
    
    async def update_user_profile(self, user_id: str, profile_data: Profile):
        path = f"/api/users/{user_id}/profile"
        return await self._make_management_request(
            method="PATCH",
            path=path,
            json_data={
                "profile": profile_data.model_dump(by_alias=True, exclude_none=True)
            },
            success_status=200,
            response_model=Profile,
            error_message_prefix=f"Failed to update logTo user profile {user_id}"
        )
    
    async def update_password(self, user_id: str, password: str):
        if len(password) < 1:
            raise Error("Min pwd length is 1 symbol")

        path = f"/api/users/{user_id}/password"
        return await self._make_management_request(
            method="PATCH",
            path=path,
            json_data={
                "password": password
            },
            success_status=200,
            response_model=UserCreateResponse,
            error_message_prefix=f"Failed to update logTo user pwd {user_id}"
        )

    async def verify_password(self, user_id: str, password: str):
        if len(password) < 1:
            raise Error("Min pwd length is 1 symbol")

        path = f"/api/users/{user_id}/password/verify"
        return await self._make_management_request(
            method="POST",
            path=path,
            json_data={
                "password": password
            },
            success_status=204,
            error_message_prefix=f"Failed to verify logTo user pwd {user_id}"
        )
    
    
    async def check_password_exists(self, user_id: str):
        path = f"/api/users/{user_id}/has-password"
        resp = await self._make_management_request(
            method="GET",
            path=path,
            success_status=200,
            error_message_prefix=f"Failed to check logTo user pwd {user_id}"
        )
        if not resp:
            return False
        
        return resp['hasPassword']
        
    
        
    













