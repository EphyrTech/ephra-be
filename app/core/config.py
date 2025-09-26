import os
from typing import List, Union, Dict, Any

from httpcore import stream
from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/v1"
    PROJECT_NAME: str = "Ephra API"
    VERSION: str = "1.0.0"
    ENV: str = Field(default="dev", alias="ENV")
    DEBUG: bool = Field(default=False, alias="DEBUG")

    # Security
    SECRET_KEY: str = Field(default="your-secret-key-for-development", alias="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30 * 24 * 60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Database
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@db:5432/mental_health_db", alias="DATABASE_URL")

    # CORS
    @property
    def CORS_ORIGINS(self) -> List[str]:
        if self.ENV == "dev":
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:19006",  # Expo development server
                "http://127.0.0.1:19006",
                "http://localhost:8081",   # React Native Metro bundler
                "http://127.0.0.1:8081",
                "http://localhost:19000",  # Expo CLI
                "http://127.0.0.1:19000",
                "*"  # Allow all origins in development
            ]
        else:
            cors_origins = os.getenv("CORS_ORIGINS", "*")
            if cors_origins:
                return [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
            return ["*"]


    # Logto Configuration
    LOGTO_ENDPOINT: str = Field(default="", alias="LOGTO_ENDPOINT", description="url of logto server")
    LOGTO_FE_APP_ID: str = Field(default="", alias="LOGTO_FE_APP_ID", description="id of the FE SPA app")
    LOGTO_APP_ID: str = Field(default="", alias="LOGTO_APP_ID", description="M2M App ID")
    LOGTO_APP_SECRET: str = Field(default="", alias="LOGTO_APP_SECRET", description="M2M App Secret")

    # Logto RBAC Configuration
    LOGTO_API_RESOURCE: str = Field(default="https://127.0.0.1:3000", alias="LOGTO_API_RESOURCE", description="API identifier")

    # Note: Redirect URIs are now handled dynamically by the frontend
    # The backend only validates JWT tokens and doesn't need static redirect URIs
    LOGTO_REDIRECT_URI: str = Field(default="", alias="LOGTO_REDIRECT_URI")
    LOGTO_POST_LOGOUT_REDIRECT_URI: str = Field(default="", alias="LOGTO_POST_LOGOUT_REDIRECT_URI")

    # File Storage
    UPLOAD_DIRECTORY: str = Field(default="uploads", alias="UPLOAD_DIRECTORY")
    MAX_UPLOAD_SIZE: int = Field(default=10 * 1024 * 1024, alias="MAX_UPLOAD_SIZE")  # 10 MB

    EMAIL_FROM: str = Field(default="care@ephyrtech.com", alias="EMAIL_FROM")

    # Mailgun settings for appointment reminders
    MAILGUN_API_KEY: str = Field(default="", alias="MAILGUN_API_KEY")
    MAILGUN_DOMAIN: str = Field(default="", alias="MAILGUN_DOMAIN")
    MAILGUN_BASE_URL: str = Field(default="https://api.eu.mailgun.net/v3", alias="MAILGUN_BASE_URL")
    MAILGUN_WEBHOOK_SIGNING_KEY: str = Field(default="", alias="MAILGUN_WEBHOOK_SIGNING_KEY")
    APPOINTMENT_REMINDER_TEMPLATE: str = Field(default="15min_before_appointment", alias="APPOINTMENT_REMINDER_TEMPLATE")

    # Frontend URL for links in emails
    FRONTEND_URL: str = Field(default="http://localhost:8001", alias="FRONTEND_URL")

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")

    # Caching
    CACHE_TTL_SECONDS: int = Field(default=300, alias="CACHE_TTL_SECONDS")  # 5 minutes

    # Logging
    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")
    LOG_FILE: str = Field(default="logs/app.log", alias="LOG_FILE")

    # WebSockets
    WS_MESSAGE_QUEUE_SIZE: int = Field(default=100, alias="WS_MESSAGE_QUEUE_SIZE")

    # Superadmin credentials for admin panel
    SUPERADMIN_USERNAME: str = Field(default="Admin", alias="SUPERADMIN_USERNAME")
    SUPERADMIN_PASSWORD: str = Field(default="super_secure_admin_2024!", alias="SUPERADMIN_PASSWORD")
    ADMIN_PANEL_SECRET_KEY: str = Field(default="admin_panel_secret_key_2024", alias="ADMIN_PANEL_SECRET_KEY")

    # Meeting link generation
    MEETING_LINK_BASE_URL: str = Field(default="https://meet.jit.si", alias="MEETING_LINK_BASE_URL")
    RUN_MIGRATIONS_ON_STARTUP: bool = Field(default=True, alias="RUN_MIGRATIONS_ON_STARTUP")

    ROLES_MAP_STRING: str = Field(default="dbrole:logtorole:logtoid,dbrole1:logtorole1:logtoid1", alias="ROLES_MAP_STRING")

    roles_map: Dict[str, Dict[str, str]] = Field(
        default="dbrole:logtorole:logtoid,dbrole1:logtorole1:logtoid1", 
        alias="ROLES_MAP" 
    )
    
    @field_validator('roles_map', mode='before')
    @classmethod
    def parse_roles_map(cls, value: Any, info: ValidationInfo) -> Dict[str, List[str]]:
        """
        Processes the input string from the original alias before assigning it
        to the 'roles_map' attribute.
        """
        # We must access the raw input string field defined above.
        # It's passed via the ValidationInfo context when using 'mode=before' 
        # for a synthetic field (or using the source input field name).
        
        # Access the raw string value (this step can be tricky depending on how V2 is loaded. 
        # A simpler way is to validate the raw string itself and pass it directly)
        
        # Let's pivot and validate the raw string directly and use a model_data handler
        # OR simplify the loader:

        # --- SIMPLER APPROACH: Validating the raw string and passing it back as the parsed Dict ---
        
        # The key here is that when ROLES_MAP is loaded from the environment/source, 
        # Pydantic attempts to assign it to *all* fields that have matching aliases or names.
        
        # If we use `info.data.get('ROLES_MAP')` to grab the raw string:
        
        raw_string = info.data.get('ROLES_MAP') or info.data.get('ROLES_MAP_STRING')

        roles_map: Dict[str, Dict[str, str]] = {}
        
        if not raw_string:
            return roles_map

        individual_mappings = raw_string.split(',')
        
        for mapping in individual_mappings:
            mapping = mapping.strip()
            if not mapping:
                continue

            parts = mapping.split(':')
            
            if len(parts) == 3:
                db_role = parts[0].strip()
                logto_role = parts[1].strip()
                logto_id = parts[2].strip()
                roles_map[db_role] = {"logto_role":logto_role, "logto_id":logto_id}
            else:
                # In a real app, use logging.warning
                print(f"Warning: Skipping malformed role mapping entry: {mapping}")

        return roles_map

def get_settings() -> Settings:
    """Get the global settings instance."""
    if not hasattr(get_settings, "_instance"):
        get_settings._instance = Settings()
    return get_settings._instance


settings = get_settings()
