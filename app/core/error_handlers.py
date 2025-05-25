"""Centralized error handling for the application"""

import logging
from typing import Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from app.services.exceptions import (
    ServiceException,
    ValidationError as ServiceValidationError,
    NotFoundError,
    PermissionError,
    ConflictError,
    BusinessRuleError
)

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling"""
    
    @staticmethod
    def create_error_response(
        status_code: int,
        message: str,
        error_code: str = None,
        details: Dict[str, Any] = None
    ) -> JSONResponse:
        """Create a standardized error response"""
        content = {
            "error": {
                "message": message,
                "code": error_code,
                "details": details or {}
            }
        }
        return JSONResponse(status_code=status_code, content=content)


def service_exception_handler(request: Request, exc: ServiceException) -> JSONResponse:
    """Handle service layer exceptions"""
    logger.warning(f"Service exception: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": request.url.path
    })
    
    # Map service exceptions to HTTP status codes
    status_map = {
        ServiceValidationError: status.HTTP_400_BAD_REQUEST,
        NotFoundError: status.HTTP_404_NOT_FOUND,
        PermissionError: status.HTTP_403_FORBIDDEN,
        ConflictError: status.HTTP_409_CONFLICT,
        BusinessRuleError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    
    status_code = status_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return ErrorHandler.create_error_response(
        status_code=status_code,
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details
    )


def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {exc}", extra={"path": request.url.path})
    
    details = {}
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"])
        details[field] = error["msg"]
    
    return ErrorHandler.create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Validation failed",
        error_code="VALIDATION_ERROR",
        details=details
    )


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions"""
    logger.warning(f"HTTP exception: {exc.detail}", extra={
        "status_code": exc.status_code,
        "path": request.url.path
    })
    
    return ErrorHandler.create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code="HTTP_ERROR"
    )


def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database errors"""
    logger.error(f"Database error: {exc}", extra={"path": request.url.path})
    
    return ErrorHandler.create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="A database error occurred",
        error_code="DATABASE_ERROR"
    )


def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {exc}", extra={"path": request.url.path}, exc_info=True)
    
    return ErrorHandler.create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred",
        error_code="INTERNAL_ERROR"
    )
