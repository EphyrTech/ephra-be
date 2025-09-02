import os
from typing import List, Union

from pydantic_settings import BaseSettings
from pydantic import Field


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
    LOGTO_ENDPOINT: str = Field(default="", alias="LOGTO_ENDPOINT")
    LOGTO_APP_ID: str = Field(default="", alias="LOGTO_APP_ID")
    LOGTO_APP_SECRET: str = Field(default="", alias="LOGTO_APP_SECRET")
    LOGTO_MANAGEMENT_APP_ID: str = Field(default="", alias="LOGTO_MANAGEMENT_APP_ID")
    LOGTO_MANAGEMENT_APP_SECRET: str = Field(default="", alias="LOGTO_MANAGEMENT_APP_SECRET")

    # Note: Redirect URIs are now handled dynamically by the frontend
    # The backend only validates JWT tokens and doesn't need static redirect URIs

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

def get_settings() -> Settings:
    """Get the global settings instance."""
    if not hasattr(get_settings, "_instance"):
        get_settings._instance = Settings()
    return get_settings._instance


settings = get_settings()
