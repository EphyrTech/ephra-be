"""Admin panel authentication and session management"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib

from fastapi import Request, HTTPException, status, Depends
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory session store (in production, use Redis or database)
admin_sessions = {}

class AdminSession:
    def __init__(self, session_id: str, username: str, ip_address: str, user_agent: str):
        self.session_id = session_id
        self.username = username
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(hours=8)  # 8 hour session

    def is_valid(self) -> bool:
        return datetime.utcnow() < self.expires_at

    def update_activity(self):
        self.last_activity = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expires_at": self.expires_at.isoformat()
        }

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    # Check for forwarded headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection
    if hasattr(request.client, 'host'):
        return request.client.host
    
    return "unknown"

def get_user_agent(request: Request) -> str:
    """Get user agent from request"""
    return request.headers.get("User-Agent", "unknown")

def authenticate_superadmin(username: str, password: str) -> bool:
    """Authenticate superadmin credentials"""
    return (username == settings.SUPERADMIN_USERNAME and 
            password == settings.SUPERADMIN_PASSWORD)

def create_admin_session(username: str, ip_address: str, user_agent: str) -> str:
    """Create a new admin session"""
    session_id = secrets.token_urlsafe(32)
    session = AdminSession(session_id, username, ip_address, user_agent)
    admin_sessions[session_id] = session
    
    # Log session creation
    logger.info(f"Admin session created - User: {username}, IP: {ip_address}, Session: {session_id}")
    
    return session_id

def get_admin_session(session_id: str) -> Optional[AdminSession]:
    """Get admin session by ID"""
    if not session_id:
        return None
    
    session = admin_sessions.get(session_id)
    if not session:
        return None
    
    if not session.is_valid():
        # Clean up expired session
        del admin_sessions[session_id]
        return None
    
    session.update_activity()
    return session

def invalidate_admin_session(session_id: str) -> bool:
    """Invalidate admin session"""
    if session_id in admin_sessions:
        session = admin_sessions[session_id]
        logger.info(f"Admin session invalidated - User: {session.username}, IP: {session.ip_address}, Session: {session_id}")
        del admin_sessions[session_id]
        return True
    return False

def cleanup_expired_sessions():
    """Clean up expired sessions"""
    expired_sessions = []
    for session_id, session in admin_sessions.items():
        if not session.is_valid():
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del admin_sessions[session_id]

def require_admin_session(request: Request) -> AdminSession:
    """Dependency to require valid admin session"""
    # Clean up expired sessions periodically
    cleanup_expired_sessions()
    
    # Get session ID from cookie
    session_id = request.cookies.get("admin_session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    session = get_admin_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session"
        )
    
    # Verify IP address for additional security
    current_ip = get_client_ip(request)
    if session.ip_address != current_ip:
        logger.warning(f"Admin session IP mismatch - Session IP: {session.ip_address}, Current IP: {current_ip}")
        invalidate_admin_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session security violation"
        )
    
    return session

def log_admin_action(session: AdminSession, action: str, details: dict = None):
    """Log admin actions for audit trail"""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "admin_user": session.username,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "action": action,
        "session_id": session.session_id
    }
    
    if details:
        log_data["details"] = details
    
    # Log to both application logger and a separate admin audit log
    logger.info(f"ADMIN_ACTION: {log_data}")
    
    # You could also write to a separate audit log file or database table
    # audit_logger = logging.getLogger("admin_audit")
    # audit_logger.info(log_data)
