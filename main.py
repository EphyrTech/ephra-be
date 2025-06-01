import time
import uvicorn
from fastapi import FastAPI, Request, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.error_handlers import (
    service_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    database_exception_handler,
    general_exception_handler
)
from app.services.exceptions import ServiceException
from app.middleware import RateLimiter, CacheMiddleware
from app.api import auth, users, journals, media, appointments, specialists, admin, care_providers
from app.api import health, metrics, websockets

# Setup logging
logger = setup_logging()

# Create the FastAPI app with full OpenAPI support
# We'll control access to docs via middleware instead of disabling OpenAPI entirely
app = FastAPI(
    title="Mental Health API",
    description="""
    A comprehensive API for mental health applications with features including:

    * User authentication and profile management
    * Journal entries for tracking thoughts and emotions
    * Appointment scheduling with specialists
    * Media file uploads
    * Specialist information and availability

    ## Authentication

    Most endpoints require authentication using JWT Bearer tokens.
    First, obtain a token using the `/auth/login` or `/auth/google` endpoints.
    Then include the token in the Authorization header of your requests:

    `Authorization: Bearer your_token_here`
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Operations for user authentication and authorization"
        },
        {
            "name": "Users",
            "description": "Operations with user profiles and account management"
        },
        {
            "name": "Journals",
            "description": "Journal entry creation, retrieval, and management"
        },
        {
            "name": "Appointments",
            "description": "Appointment scheduling and management with specialists"
        },
        {
            "name": "Specialists",
            "description": "Specialist information, profiles, and availability"
        },
        {
            "name": "Admin",
            "description": "Administrative functions for user and role management"
        },
        {
            "name": "Media",
            "description": "Media file uploads and management"
        },
        {
            "name": "Health",
            "description": "API health check endpoints"
        },
        {
            "name": "Monitoring",
            "description": "Monitoring and metrics endpoints"
        }
    ],
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)

# Log CORS configuration for debugging
logger.info(f"🌐 CORS Origins configured: {settings.CORS_ORIGINS}")
logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")

# Configure CORS with more options
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],  # Useful for pagination
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Middleware to block documentation endpoints in production
@app.middleware("http")
async def block_docs_in_production(request: Request, call_next):
    if settings.ENVIRONMENT == "production":
        # Block access to documentation endpoints in production
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            logger.warning(f"🔒 Blocked access to documentation endpoint: {request.url.path}")
            raise HTTPException(
                status_code=404,
                detail="Not Found"
            )

    response = await call_next(request)
    return response

# Log documentation access status
if settings.ENVIRONMENT == "production":
    logger.info("🔒 API documentation access blocked in production environment")
else:
    logger.info(f"📚 API documentation enabled for {settings.ENVIRONMENT} environment")
    logger.info("   - Swagger UI: /docs")
    logger.info("   - ReDoc: /redoc")
    logger.info("   - OpenAPI JSON: /openapi.json")

# Let CORS middleware handle all OPTIONS requests automatically

# Add other middleware after CORS
app.add_middleware(RateLimiter)
app.add_middleware(CacheMiddleware)

# Add error handlers
app.add_exception_handler(ServiceException, service_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # Log request details
    logger.info(f"{request.method} {request.url.path} {response.status_code} "
          f"Completed in {process_time:.4f}s")

    return response

# API versioning
v1_router = APIRouter(prefix="/v1")

# Include routers in v1
v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(users.router, prefix="/users", tags=["Users"])
v1_router.include_router(journals.router, prefix="/journals", tags=["Journals"])
v1_router.include_router(media.router, prefix="/media", tags=["Media"])
v1_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
v1_router.include_router(specialists.router, prefix="/specialists", tags=["Specialists"])
v1_router.include_router(care_providers.router, prefix="/care-providers", tags=["Care Providers"])
v1_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
v1_router.include_router(health.router, tags=["Health"])
v1_router.include_router(metrics.router, tags=["Monitoring"])
v1_router.include_router(websockets.router, tags=["WebSockets"])

# Include versioned router in the main app
app.include_router(v1_router)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Static directory not found, skipping static files mounting: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to Mental Health API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
