import os
from typing import List, Union
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/v1"
    PROJECT_NAME: str = "Mental Health API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-for-development")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 * 24 * 60  # 30 days

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@db:5432/mental_health_db"
    )

    # CORS
    @property
    def CORS_ORIGINS(self) -> List[str]:
        if self.ENVIRONMENT == "development":
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

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # Logto Configuration
    LOGTO_ENDPOINT: str = os.getenv("LOGTO_ENDPOINT", "https://logto-wkc0gogw84o0g4owkswswc80.ephyrtech.com/")
    LOGTO_APP_ID: str = os.getenv("LOGTO_APP_ID", "ttybvspaqdfky02zlxztd")
    LOGTO_APP_SECRET: str = os.getenv("LOGTO_APP_SECRET", "cqyOfssoPOos02yuTAIv3qE4op0u6BRA")
    LOGTO_REDIRECT_URI: str = os.getenv("LOGTO_REDIRECT_URI", "http://localhost:8000/v1/auth/logto/callback")

    @property
    def LOGTO_POST_LOGOUT_REDIRECT_URI(self) -> str:
        """Get the post-logout redirect URI, defaulting to frontend URL."""
        return os.getenv("LOGTO_POST_LOGOUT_REDIRECT_URI", self.FRONTEND_URL)

    # File Storage
    UPLOAD_DIRECTORY: str = os.getenv("UPLOAD_DIRECTORY", "uploads")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))  # 10 MB

    # Email settings
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@example.com")

    # Frontend URL for links in emails
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8001")

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    # Caching
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")

    # WebSockets
    WS_MESSAGE_QUEUE_SIZE: int = int(os.getenv("WS_MESSAGE_QUEUE_SIZE", "100"))

settings = Settings()
