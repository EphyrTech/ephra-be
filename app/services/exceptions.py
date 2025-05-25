"""Custom service layer exceptions"""

from typing import Optional, Dict, Any


class ServiceException(Exception):
    """Base exception for service layer"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ServiceException):
    """Raised when business validation fails"""
    pass


class NotFoundError(ServiceException):
    """Raised when a resource is not found"""
    pass


class PermissionError(ServiceException):
    """Raised when user lacks permission for an operation"""
    pass


class ConflictError(ServiceException):
    """Raised when there's a conflict (e.g., time slot already booked)"""
    pass


class BusinessRuleError(ServiceException):
    """Raised when a business rule is violated"""
    pass
