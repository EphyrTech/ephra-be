"""Admin panel routes with Jinja2 templates and comprehensive logging"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pendulum
from fastapi import (APIRouter, Depends, Form, HTTPException, Request,
                     Response, status)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.core.admin_auth import (AdminSession, admin_sessions,
                                 authenticate_superadmin, create_admin_session,
                                 get_admin_session, get_client_ip,
                                 get_user_agent, invalidate_admin_session,
                                 log_admin_action)
from app.core.config import settings
from app.db.database import get_db
from app.db.models import (Appointment, AppointmentStatus, Availability,
                           CareProviderProfile, Journal, MediaFile,
                           PersonalJournal, SpecialistType, User, UserRole,
                           generate_uuid)
from app.middleware import invalidate_cache

logger = logging.getLogger(__name__)

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

def add_no_cache_headers(response):
    """Add headers to prevent caching of admin pages"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Router with uncommon path for security
router = APIRouter(prefix="/admin-control-panel-x7k9m2", tags=["Admin Panel"])

def get_admin_session_or_redirect(request: Request):
    """Get admin session or return redirect response"""
    try:
        # Clean up expired sessions periodically
        from app.core.admin_auth import (cleanup_expired_sessions,
                                         get_admin_session,
                                         invalidate_admin_session)
        cleanup_expired_sessions()

        # Get session ID from cookie
        session_id = request.cookies.get("admin_session_id")
        if not session_id:
            return None

        session = get_admin_session(session_id)
        if not session:
            return None

        # Verify IP address for additional security
        current_ip = get_client_ip(request)
        if session.ip_address != current_ip:
            logger.warning(f"Admin session IP mismatch - Session IP: {session.ip_address}, Current IP: {current_ip}")
            invalidate_admin_session(session_id)
            return None

        return session
    except Exception:
        return None

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: Optional[str] = None):
    """Display admin login page"""
    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "error": error
    })

@router.post("/login")
async def admin_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle admin login"""
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Log login attempt
    logger.info(f"Admin login attempt - Username: {username}, IP: {ip_address}")
    
    if not authenticate_superadmin(username, password, db):
        logger.warning(f"Failed admin login attempt - Username: {username}, IP: {ip_address}")
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Invalid credentials"
        }, status_code=401)
    user = db.query(User).filter(User.display_name == username).first()
    # Create session
    session_id = create_admin_session(username, ip_address, user_agent, user.id)
    
    # Set secure cookie
    response = RedirectResponse(url="/admin-control-panel-x7k9m2/dashboard", status_code=302)
    response.set_cookie(
        key="admin_session_id",
        value=session_id,
        max_age=8 * 60 * 60,  # 8 hours
        httponly=True,
        secure=settings.ENV == "prod",
        samesite="strict"
    )
    
    logger.info(f"Successful admin login - Username: {username}, IP: {ip_address}, Session: {session_id}")
    return response

@router.get("/logout")
async def admin_logout(
    request: Request,
    response: Response
):
    """Handle admin logout"""
    # Try to get session for logging, but don't require it
    session = get_admin_session_or_redirect(request)

    session_id = request.cookies.get("admin_session_id")
    if session_id:
        invalidate_admin_session(session_id)

    response = RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)
    response.delete_cookie("admin_session_id")

    if session:
        log_admin_action(session, "LOGOUT")
    return response

@router.get("/session-info")
async def session_info(request: Request):
    """Get current session info for AJAX checks"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)
    return {"valid": True, "session": session.to_dict()}

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    """Admin dashboard with statistics and overview"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_DASHBOARD")
    
    # Get statistics
    stats = {
        "total_users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),
        "total_journals": db.query(Journal).count(),
        "total_appointments": db.query(Appointment).count(),
    }
    
    # Get recent activity (last 10 users)
    recent_activity = db.query(User).order_by(desc(User.created_at)).limit(10).all()
    activity_list = []
    for user in recent_activity:
        activity_list.append({
            "user_name": user.name or user.display_name,
            "user_email": user.email,
            "action": "User Registration",
            "created_at": user.created_at,
            "status": "active" if user.is_active else "inactive"
        })
    
    # System information
    system_info = {
        "environment": settings.ENV,
        "database_status": "Connected",
        "active_admin_sessions": len(admin_sessions),
        "server_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "uptime": "N/A"  # Could be calculated if needed
    }
    
    # Chart data (last 7 days)
    chart_data = get_dashboard_chart_data(db)
    
    response = templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "session": session,
        "stats": stats,
        "recent_activity": activity_list,
        "system_info": system_info,
        "chart_data": chart_data
    })
    return add_no_cache_headers(response)

def get_dashboard_chart_data(db: Session) -> Dict[str, Any]:
    """Get chart data for dashboard"""
    # User registration trend (last 7 days)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=6)
    
    user_registration_data = []
    user_registration_labels = []
    
    for i in range(7):
        date = start_date + timedelta(days=i)
        count = db.query(User).filter(
            func.date(User.created_at) == date
        ).count()
        user_registration_data.append(count)
        user_registration_labels.append(date.strftime("%m/%d"))
    
    # Journal entries (last 7 days)
    journal_entries_data = []
    journal_entries_labels = []
    
    for i in range(7):
        date = start_date + timedelta(days=i)
        count = db.query(Journal).filter(
            func.date(Journal.created_at) == date
        ).count()
        journal_entries_data.append(count)
        journal_entries_labels.append(date.strftime("%m/%d"))
    
    return {
        "user_registration_labels": user_registration_labels,
        "user_registration_data": user_registration_data,
        "journal_entries_labels": journal_entries_labels,
        "journal_entries_data": journal_entries_data
    }

@router.get("/users", response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None
):
    """List all users with pagination and search"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_USERS", {"page": page, "search": search})
    
    query = db.query(User)
    
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) |
            (User.name.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%"))
        )
    
    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("admin/users_list.html", {
        "request": request,
        "session": session,
        "users": users,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "search": search or ""
    })

@router.get("/sessions", response_class=HTMLResponse)
async def admin_sessions_list(
    request: Request,
    
):
    """List active admin sessions"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)
    
    log_admin_action(session, "VIEW_SESSIONS")
    
    return templates.TemplateResponse("admin/sessions.html", {
        "request": request,
        "session": session,
        "sessions": list(admin_sessions.values())
    })

@router.get("/audit-log", response_class=HTMLResponse)
async def admin_audit_log(
    request: Request,
    page: int = 1,
    per_page: int = 50
):
    """Display audit log of admin actions"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_AUDIT_LOG", {"page": page})

    # Get real audit entries from the in-memory audit log
    from app.core.admin_auth import get_audit_log_entries
    audit_entries = get_audit_log_entries(page, per_page)

    return templates.TemplateResponse("admin/audit_log.html", {
        "request": request,
        "session": session,
        "audit_entries": audit_entries,
        "page": page,
        "per_page": per_page
    })

# User CRUD endpoints - CREATE routes must come before parameterized routes
@router.get("/users/create", response_class=HTMLResponse)
async def admin_user_create_form(
    request: Request,

):
    """Show user creation form"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_USER_CREATE_FORM")
    return templates.TemplateResponse("admin/user_create.html", {
        "request": request,
        "session": session
    })

@router.post("/users/create")
async def admin_user_create(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new user"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return {"success": False, "message": "Authentication required"}

    try:
        user_data = await request.json()
        log_admin_action(session, "CREATE_USER", {"email": user_data.get("email")})

        import uuid

        from app.core.security import get_password_hash
        from app.db.models import CareProviderProfile, SpecialistType

        # Create user
        new_user = User(
            id=str(uuid.uuid4()),
            email=user_data["email"],
            hashed_password=get_password_hash(user_data["password"]),
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            name=user_data.get("display_name"),
            phone_number=user_data.get("phone_number"),
            role=UserRole(user_data.get("role", "user")),
            is_active=user_data.get("is_active", True)
        )
        db.add(new_user)

        # If care provider, create profile
        if new_user.role == UserRole.CARE_PROVIDER:
            care_profile = CareProviderProfile(
                id=str(uuid.uuid4()),
                user_id=new_user.id,
                license_number=user_data.get("license_number"),
                specialty=SpecialistType(user_data.get("specialty", "mental")),
                hourly_rate=user_data.get("hourly_rate"),
                bio=user_data.get("bio")
            )
            db.add(care_profile)

            # Create availability slots if provided
            availability_slots = user_data.get("availability_slots", [])
            if availability_slots:
                from datetime import datetime

                from app.db.models import Availability

                for slot_data in availability_slots:
                    try:
                        # Parse datetime strings
                        start_time = datetime.fromisoformat(slot_data["start_time"])
                        end_time = datetime.fromisoformat(slot_data["end_time"])

                        availability = Availability(
                            id=str(uuid.uuid4()),
                            care_provider_id=care_profile.id,
                            start_time=start_time,
                            end_time=end_time,
                            is_available=slot_data.get("is_available", True)
                        )
                        db.add(availability)
                    except (ValueError, KeyError) as e:
                        # Skip invalid availability slots
                        continue

        db.commit()

        # Invalidate cache after user creation
        invalidate_cache()

        return {"success": True, "message": "User created successfully", "user_id": new_user.id}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error creating user: {str(e)}"}

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db)
):
    """View user details"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_USER_DETAIL", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's journals
    journals = db.query(Journal).filter(Journal.user_id == user_id).order_by(desc(Journal.created_at)).limit(10).all()

    # Get user's appointments
    appointments = db.query(Appointment).filter(Appointment.user_id == user_id).order_by(desc(Appointment.created_at)).limit(10).all()

    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request,
        "session": session,
        "user": user,
        "journals": journals,
        "appointments": appointments
    })

@router.post("/users/{user_id}/activate")
async def admin_activate_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Activate user"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    log_admin_action(session, "ACTIVATE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    user.is_active = True
    db.commit()

    # Invalidate cache after user activation
    invalidate_cache()

    return {"success": True, "message": "User activated successfully"}

@router.post("/users/{user_id}/deactivate")
async def admin_deactivate_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Deactivate user"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    log_admin_action(session, "DEACTIVATE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    user.is_active = False
    db.commit()

    # Invalidate cache after user deactivation
    invalidate_cache()

    return {"success": True, "message": "User deactivated successfully"}

@router.post("/users/{user_id}/delete")
async def admin_delete_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete user (soft delete by deactivating)"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    log_admin_action(session, "DELETE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    # Soft delete by deactivating
    user.is_active = False
    db.commit()

    # Invalidate cache after user deletion
    invalidate_cache()

    return {"success": True, "message": "User deleted successfully"}

@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
async def admin_user_edit_form(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Show user edit form"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_USER_EDIT_FORM", {"user_id": user_id})

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("admin/user_edit.html", {
        "request": request,
        "user": user,
        "session": session
    })

@router.post("/users/{user_id}/edit")
async def admin_user_edit(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Update user"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    # Get form data
    body = await request.json()

    log_admin_action(session, "EDIT_USER", {
        "user_id": user_id,
        "changes": body
    })

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user fields
    if "full_name" in body:
        user.full_name = body["full_name"]
    if "email" in body:
        # Check if email is already taken by another user
        existing_user = db.query(User).filter(
            User.email == body["email"],
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = body["email"]
    if "role" in body:
        user.role = body["role"]
    if "is_active" in body:
        user.is_active = body["is_active"]

    # Update timestamps
    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    # Invalidate cache after user update
    invalidate_cache()

    return {"success": True, "message": "User updated successfully", "user": {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    }}

@router.get("/journals", response_class=HTMLResponse)
async def admin_journals_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all journals"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_JOURNALS", {"page": page})

    query = db.query(Journal).options(joinedload(Journal.user)).order_by(desc(Journal.created_at))
    total = query.count()
    journals = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/journals_list.html", {
        "request": request,
        "session": session,
        "journals": journals,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

@router.get("/appointments", response_class=HTMLResponse)
async def admin_appointments_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all appointments"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_APPOINTMENTS", {"page": page})

    query = db.query(Appointment).options(
        joinedload(Appointment.user),
        joinedload(Appointment.care_provider)
    ).order_by(desc(Appointment.created_at))

    total = query.count()
    appointments = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/appointments_list.html", {
        "request": request,
        "session": session,
        "appointments": appointments,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

@router.get("/care-providers", response_class=HTMLResponse)
async def admin_care_providers_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all care providers"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_CARE_PROVIDERS", {"page": page})

    query = db.query(User).filter(User.role == UserRole.CARE_PROVIDER).options(
        joinedload(User.care_provider_profile)
    ).order_by(desc(User.created_at))

    total = query.count()
    care_providers = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/care_providers_list.html", {
        "request": request,
        "session": session,
        "care_providers": care_providers,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

@router.get("/media", response_class=HTMLResponse)
async def admin_media_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all media files"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_MEDIA", {"page": page})

    query = db.query(MediaFile).options(joinedload(MediaFile.user)).order_by(desc(MediaFile.created_at))
    total = query.count()
    media_files = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/media_list.html", {
        "request": request,
        "session": session,
        "media_files": media_files,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

@router.get("/personal-journals", response_class=HTMLResponse)
async def admin_personal_journals_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all personal journals"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_PERSONAL_JOURNALS", {"page": page})

    query = db.query(PersonalJournal).options(
        joinedload(PersonalJournal.patient),
        joinedload(PersonalJournal.author)
    ).order_by(desc(PersonalJournal.created_at))

    total = query.count()
    personal_journals = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/personal_journals_list.html", {
        "request": request,
        "session": session,
        "personal_journals": personal_journals,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

@router.get("/availability", response_class=HTMLResponse)
async def admin_availability_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all availability slots"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_AVAILABILITY", {"page": page})

    from sqlalchemy import func

    from app.db.models import Appointment, AppointmentStatus

    # First, let's get availability slots with proper user info
    availability_query = db.query(Availability).options(
        joinedload(Availability.care_provider).joinedload(CareProviderProfile.user)
    ).order_by(desc(Availability.created_at))

    availability_slots_raw = availability_query.offset((page - 1) * per_page).limit(per_page).all()

    # Now add appointment counts for each slot
    availability_slots = []
    for slot in availability_slots_raw:
        # Count appointments that overlap with this availability slot
        appointment_count = db.query(Appointment).filter(
            Appointment.care_provider_id == slot.care_provider.user_id,
            Appointment.start_time < slot.end_time,
            Appointment.end_time > slot.start_time,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).count()

        slot.appointment_count = appointment_count
        availability_slots.append(slot)

    total = db.query(Availability).count()

    total_pages = (total + per_page - 1) // per_page

    response = templates.TemplateResponse("admin/availability_list.html", {
        "request": request,
        "session": session,
        "availability_slots": availability_slots,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })
    return add_no_cache_headers(response)

@router.get("/availability/{slot_id}", response_class=HTMLResponse)
async def admin_availability_detail(
    slot_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Show availability slot details with appointments"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_AVAILABILITY_DETAIL", {"slot_id": slot_id})

    # Get availability slot with care provider info
    slot = db.query(Availability).options(
        joinedload(Availability.care_provider).joinedload(CareProviderProfile.user)
    ).filter(Availability.id == slot_id).first()

    if not slot:
        raise HTTPException(status_code=404, detail="Availability slot not found")

    # Get appointments that overlap with this availability slot
    appointments = db.query(Appointment).options(
        joinedload(Appointment.user),
        joinedload(Appointment.care_provider)
    ).filter(
        Appointment.care_provider_id == slot.care_provider.user_id,
        Appointment.start_time < slot.end_time,
        Appointment.end_time > slot.start_time
    ).order_by(Appointment.start_time).all()

    response = templates.TemplateResponse("admin/availability_detail.html", {
        "request": request,
        "session": session,
        "slot": slot,
        "appointments": appointments
    })
    return add_no_cache_headers(response)

@router.get("/appointments/create", response_class=HTMLResponse)
async def admin_appointment_create_form(
    request: Request,
    db: Session = Depends(get_db)
):
    """Show appointment creation form"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_APPOINTMENT_CREATE_FORM", {})

    # Get all users and care providers for dropdowns
    users = db.query(User).filter(User.role == UserRole.USER, User.is_active == True).order_by(User.name).all()
    care_providers = db.query(User).filter(User.role == UserRole.CARE_PROVIDER, User.is_active == True).order_by(User.name).all()

    return templates.TemplateResponse("admin/appointment_create.html", {
        "request": request,
        "session": session,
        "users": users,
        "care_providers": care_providers
    })

@router.post("/appointments/create")
async def admin_appointment_create(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create new appointment"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    from app.services.appointment_service import (AppointmentCreate,
                                                  AppointmentService)


    try:

        session = require_admin_session(request, db)

        form_data = await request.form()
        
        appointment_data = AppointmentCreate.model_validate(form_data)

        apse = AppointmentService(db)
        user = db.query(User).filter(User.id == session.user_id).first()
        appointment = apse.create_appointment(appointment_data, user)



        log_admin_action(session, "CREATE_APPOINTMENT", {
            "user_id": form_data.get("user_id"),
            "care_provider_id": form_data.get("care_provider_id")
        })


        return RedirectResponse(
            url=f"/admin-control-panel-x7k9m2/appointments/{appointment.id}",
            status_code=302
        )

    except Exception as e:
        return templates.TemplateResponse("admin/appointment_create.html", {
            "request": request,
            "session": session,
            "users": db.query(User).filter(User.role == UserRole.USER, User.is_active == True).order_by(User.name).all(),
            "care_providers": db.query(User).filter(User.role == UserRole.CARE_PROVIDER, User.is_active == True).order_by(User.name).all(),
            "error": f"Error creating appointment: {str(e)}"
        })

# Additional CRUD endpoints for actions called by the UI

@router.get("/journals/{journal_id}", response_class=HTMLResponse)
async def admin_journal_detail(
    journal_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Show journal details"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_JOURNAL_DETAIL", {"journal_id": journal_id})

    journal = db.query(Journal).options(
        joinedload(Journal.user)
    ).filter(Journal.id == journal_id).first()

    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found")

    return templates.TemplateResponse("admin/journal_detail.html", {
        "request": request,
        "session": session,
        "journal": journal
    })

@router.post("/journals/{journal_id}/delete")
async def admin_delete_journal(
    journal_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete journal entry"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    log_admin_action(session, "DELETE_JOURNAL", {"journal_id": journal_id})

    journal = db.query(Journal).filter(Journal.id == journal_id).first()
    if not journal:
        return {"success": False, "message": "Journal not found"}

    db.delete(journal)
    db.commit()

    # Invalidate cache after journal deletion
    invalidate_cache()

    return {"success": True, "message": "Journal deleted successfully"}

@router.get("/appointments/{appointment_id}", response_class=HTMLResponse)
async def admin_appointment_detail(
    appointment_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Show appointment details"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)

    log_admin_action(session, "VIEW_APPOINTMENT_DETAIL", {"appointment_id": appointment_id})

    appointment = db.query(Appointment).options(
        joinedload(Appointment.user),
        joinedload(Appointment.care_provider)
    ).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return templates.TemplateResponse("admin/appointment_detail.html", {
        "request": request,
        "session": session,
        "appointment": appointment
    })

@router.post("/appointments/{appointment_id}/status")
async def admin_update_appointment_status(
    appointment_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update appointment status"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    body = await request.json()
    new_status = body.get("status")

    log_admin_action(session, "UPDATE_APPOINTMENT_STATUS", {
        "appointment_id": appointment_id,
        "new_status": new_status
    })

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        return {"success": False, "message": "Appointment not found"}

    try:
        # Update the status as string value
        appointment.status = new_status
        db.commit()

        # Invalidate cache after appointment status update
        invalidate_cache()

        return {"success": True, "message": f"Appointment status updated to {new_status}"}
    except Exception as e:
        return {"success": False, "message": f"Error updating status: {str(e)}"}

@router.post("/appointments/{appointment_id}/delete")
async def admin_delete_appointment(
    appointment_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete appointment"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    log_admin_action(session, "DELETE_APPOINTMENT", {"appointment_id": appointment_id})

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        return {"success": False, "message": "Appointment not found"}

    db.delete(appointment)
    db.commit()

    # Invalidate cache after appointment deletion
    invalidate_cache()

    return {"success": True, "message": "Appointment deleted successfully"}

@router.post("/sessions/{session_id}/terminate")
async def admin_terminate_session(
    session_id: str,
    current_,
    request: Request
):
    """Terminate a specific admin session"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)
    
    log_admin_action(session, "TERMINATE_SESSION", {"terminated_session_id": session_id})

    if invalidate_admin_session(session_id):
        return {"success": True, "message": "Session terminated successfully"}
    else:
        return {"success": False, "message": "Session not found or already terminated"}

@router.post("/sessions/terminate-others")
async def admin_terminate_other_sessions(
    current_,
    request: Request
):
    """Terminate all other admin sessions except current one"""
    terminated_count = 0
    sessions_to_terminate = []

    for session_id, session in admin_sessions.items():
        if session_id != session.session_id:
            sessions_to_terminate.append(session_id)

    for session_id in sessions_to_terminate:
        if invalidate_admin_session(session_id):
            terminated_count += 1

    log_admin_action(session, "TERMINATE_OTHER_SESSIONS", {
        "terminated_count": terminated_count
    })

    return {"success": True, "terminated_count": terminated_count}

@router.get("/audit-log/live")
async def admin_audit_log_live(
    request: Request,
    
):
    """Get live audit log entries for real-time monitoring"""
    from app.core.admin_auth import get_recent_audit_entries
    recent_entries = get_recent_audit_entries(10)
    return {"entries": recent_entries}

# Additional CRUD endpoints for other entities can be added here

@router.get("/users/export")
async def admin_users_export(
    request: Request,
    db: Session = Depends(get_db)
):
    """Export users data as CSV"""
    log_admin_action(session, "EXPORT_USERS")

    import csv
    import io

    from fastapi.responses import StreamingResponse

    users = db.query(User).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['ID', 'Email', 'Name', 'Role', 'Active', 'Created'])

    # Write data
    for user in users:
        writer.writerow([
            user.id,
            user.email,
            user.name or user.display_name or '',
            user.role.value,
            user.is_active,
            user.created_at.isoformat()
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"}
    )

@router.post("/media/{media_id}/delete")
async def admin_delete_media(
    media_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete media file"""
    log_admin_action(session, "DELETE_MEDIA", {"media_id": media_id})

    media = db.query(MediaFile).filter(MediaFile.id == media_id).first()
    if not media:
        return {"success": False, "message": "Media file not found"}

    db.delete(media)
    db.commit()

    return {"success": True, "message": "Media file deleted successfully"}

@router.post("/personal-journals/{journal_id}/delete")
async def admin_delete_personal_journal(
    journal_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete personal journal entry"""
    log_admin_action(session, "DELETE_PERSONAL_JOURNAL", {"journal_id": journal_id})

    journal = db.query(PersonalJournal).filter(PersonalJournal.id == journal_id).first()
    if not journal:
        return {"success": False, "message": "Personal journal not found"}

    db.delete(journal)
    db.commit()

    return {"success": True, "message": "Personal journal deleted successfully"}

@router.post("/availability/{slot_id}/toggle")
async def admin_toggle_availability(
    slot_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Toggle availability slot status"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    body = await request.json()
    available = body.get("available", True)

    log_admin_action(session, "TOGGLE_AVAILABILITY", {
        "slot_id": slot_id,
        "available": available
    })

    slot = db.query(Availability).filter(Availability.id == slot_id).first()
    if not slot:
        return {"success": False, "message": "Availability slot not found"}

    slot.is_available = available
    db.commit()

    # Invalidate cache after availability toggle
    invalidate_cache()

    return {"success": True, "message": f"Availability slot {'enabled' if available else 'disabled'}"}

@router.post("/availability/{slot_id}/delete")
async def admin_delete_availability(
    slot_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete availability slot"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    log_admin_action(session, "DELETE_AVAILABILITY", {"slot_id": slot_id})

    # Check if there are any appointments in this slot before deleting
    from app.db.models import Appointment, AppointmentStatus

    slot = db.query(Availability).options(
        joinedload(Availability.care_provider).joinedload(CareProviderProfile.user)
    ).filter(Availability.id == slot_id).first()

    if not slot:
        return {"success": False, "message": "Availability slot not found"}

    # Check for appointments in this time slot
    appointment_count = db.query(Appointment).filter(
        Appointment.care_provider_id == slot.care_provider.user_id,
        Appointment.start_time < slot.end_time,
        Appointment.end_time > slot.start_time,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
    ).count()

    if appointment_count > 0:
        return {"success": False, "message": f"Cannot delete availability slot with {appointment_count} scheduled appointment(s)"}

    db.delete(slot)
    db.commit()

    # Invalidate cache after availability deletion
    invalidate_cache()

    return {"success": True, "message": "Availability slot deleted successfully"}

@router.post("/availability/create-pattern")
async def admin_create_availability_pattern(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create availability pattern for a care provider"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    try:
        pattern_data = await request.json()
        log_admin_action(session, "CREATE_AVAILABILITY_PATTERN", pattern_data)

        import uuid
        from datetime import datetime, time, timedelta

        from app.db.models import Appointment, AppointmentStatus

        care_provider_id = pattern_data["careProviderId"]
        day_of_week = pattern_data["dayOfWeek"]  # 0=Monday, 6=Sunday
        start_time_str = pattern_data["startTime"]  # "HH:MM"
        end_time_str = pattern_data["endTime"]  # "HH:MM"
        apply_for_month = pattern_data.get("applyForMonth", False)

        # Get care provider profile
        user = db.query(User).filter(User.id == care_provider_id).first()
        if not user or user.role != UserRole.CARE_PROVIDER:
            return {"success": False, "message": "Care provider not found"}

        care_profile = db.query(CareProviderProfile).filter(
            CareProviderProfile.user_id == care_provider_id
        ).first()
        if not care_profile:
            return {"success": False, "message": "Care provider profile not found"}

        # Parse times
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))

        created_count = 0
        conflicts = []
        suggested_ranges = []

        # Determine date range
        start_date = datetime.now().date()
        if apply_for_month:
            end_date = start_date + timedelta(days=28)  # 4 weeks
        else:
            end_date = start_date

        # Find all dates matching the day of week
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() == day_of_week:
                # Create datetime objects for this date
                slot_start = datetime.combine(current_date, time(start_hour, start_minute))
                slot_end = datetime.combine(current_date, time(end_hour, end_minute))

                # Check for appointment conflicts
                conflicting_appointments = db.query(Appointment).filter(
                    Appointment.care_provider_id == care_provider_id,
                    Appointment.start_time < slot_end,
                    Appointment.end_time > slot_start,
                    Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
                ).all()

                if conflicting_appointments:
                    conflicts.append({
                        "date": current_date.strftime('%Y-%m-%d'),
                        "appointments": len(conflicting_appointments)
                    })

                    # Generate suggested ranges for today only
                    if current_date == datetime.now().date():
                        suggested_ranges = generate_available_ranges(
                            db, care_provider_id, current_date, conflicting_appointments
                        )
                else:
                    # Check for existing availability overlap
                    overlapping = db.query(Availability).filter(
                        Availability.care_provider_id == care_profile.id,
                        Availability.start_time < slot_end,
                        Availability.end_time > slot_start,
                    ).first()

                    if not overlapping:
                        # Create availability slot
                        availability = Availability(
                            id=str(uuid.uuid4()),
                            care_provider_id=care_profile.id,
                            start_time=slot_start,
                            end_time=slot_end,
                            is_available=True
                        )
                        db.add(availability)
                        created_count += 1

            current_date += timedelta(days=1)

        db.commit()

        # Invalidate cache after availability creation
        invalidate_cache()

        if conflicts and not created_count:
            return {
                "success": False,
                "message": "Cannot create availability slots due to appointment conflicts",
                "conflicts": conflicts,
                "suggested_ranges": suggested_ranges
            }

        return {
            "success": True,
            "message": f"Created {created_count} availability slots",
            "created_count": created_count,
            "conflicts": conflicts
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error creating availability pattern: {str(e)}"}

@router.post("/availability/{slot_id}/edit")
async def admin_edit_availability(
    slot_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Edit an availability slot"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    try:
        update_data = await request.json()
        log_admin_action(session, "EDIT_AVAILABILITY", {"slot_id": slot_id, "update_data": update_data})

        from datetime import datetime

        from app.db.models import Appointment, AppointmentStatus

        # Get availability slot
        slot = db.query(Availability).options(
            joinedload(Availability.care_provider).joinedload(CareProviderProfile.user)
        ).filter(Availability.id == slot_id).first()

        if not slot:
            return {"success": False, "message": "Availability slot not found"}

        # Parse new times
        new_start = datetime.fromisoformat(update_data["start_time"])
        new_end = datetime.fromisoformat(update_data["end_time"])

        if new_start >= new_end:
            return {"success": False, "message": "Start time must be before end time"}

        # Check for appointment conflicts
        conflicting_appointments = db.query(Appointment).filter(
            Appointment.care_provider_id == slot.care_provider.user_id,
            Appointment.start_time < new_end,
            Appointment.end_time > new_start,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).all()

        if conflicting_appointments:
            # Generate suggested ranges for today
            suggested_ranges = []
            if new_start.date() == datetime.now().date():
                suggested_ranges = generate_available_ranges(
                    db, slot.care_provider.user_id, new_start.date(), conflicting_appointments
                )

            return {
                "success": False,
                "message": f"Cannot update availability due to {len(conflicting_appointments)} appointment conflict(s)",
                "suggested_ranges": suggested_ranges
            }

        # Check for overlapping availability slots (excluding current one)
        overlapping = db.query(Availability).filter(
            Availability.care_provider_id == slot.care_provider_id,
            Availability.start_time < new_end,
            Availability.end_time > new_start,
            Availability.id != slot_id
        ).first()

        if overlapping:
            return {"success": False, "message": "This time slot overlaps with an existing availability slot"}

        # Update the slot
        slot.start_time = new_start
        slot.end_time = new_end
        db.commit()

        # Invalidate cache after availability update
        invalidate_cache()

        return {"success": True, "message": "Availability slot updated successfully"}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error updating availability slot: {str(e)}"}

def generate_available_ranges(db: Session, care_provider_id: str, date, conflicting_appointments):
    """Generate suggested available time ranges for a given date"""
    from datetime import datetime, time, timedelta

    # Get current time + 20 minutes
    now = datetime.now()
    min_start_time = now + timedelta(minutes=20) if date == now.date() else datetime.combine(date, time(0, 0))
    max_end_time = datetime.combine(date, time(23, 59))

    # Get all appointments for the day
    all_appointments = db.query(Appointment).filter(
        Appointment.care_provider_id == care_provider_id,
        Appointment.start_time >= datetime.combine(date, time(0, 0)),
        Appointment.start_time < datetime.combine(date + timedelta(days=1), time(0, 0)),
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
    ).order_by(Appointment.start_time).all()

    suggested_ranges = []

    if not all_appointments:
        # No appointments, suggest the whole remaining day
        if min_start_time < max_end_time:
            suggested_ranges.append({
                "start": min_start_time.strftime('%H:%M'),
                "end": max_end_time.strftime('%H:%M')
            })
    else:
        # Find gaps between appointments
        current_time = min_start_time

        for appointment in all_appointments:
            if current_time < appointment.start_time:
                # Gap before this appointment
                suggested_ranges.append({
                    "start": current_time.strftime('%H:%M'),
                    "end": appointment.start_time.strftime('%H:%M')
                })
            current_time = max(current_time, appointment.end_time)

        # Check for time after last appointment
        if current_time < max_end_time:
            suggested_ranges.append({
                "start": current_time.strftime('%H:%M'),
                "end": max_end_time.strftime('%H:%M')
            })

    return suggested_ranges

@router.get("/api/care-providers")
async def admin_get_care_providers(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get list of care providers for admin use"""
    # Check authentication
    session = get_admin_session_or_redirect(request)
    if not session:
        return {"success": False, "message": "Authentication required"}

    try:
        care_providers = db.query(User).filter(
            User.role == UserRole.CARE_PROVIDER,
            User.is_active == True
        ).all()

        provider_list = []
        for provider in care_providers:
            provider_list.append({
                "id": provider.id,
                "email": provider.email,
                "first_name": provider.first_name,
                "last_name": provider.last_name,
                "name": provider.name
            })

        return {"success": True, "care_providers": provider_list}

    except Exception as e:
        return {"success": False, "message": f"Error fetching care providers: {str(e)}"}

@router.post("/availability/create-single")
async def admin_create_single_availability(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a single availability slot"""
    # Check authentication for API endpoints
    from app.core.admin_auth import require_admin_session
    session = require_admin_session(request)

    try:
        slot_data = await request.json()
        log_admin_action(session, "CREATE_SINGLE_AVAILABILITY", slot_data)

        import uuid
        from datetime import datetime, time

        from app.db.models import Appointment, AppointmentStatus

        care_provider_id = slot_data["careProviderId"]
        date_str = slot_data["date"]  # "YYYY-MM-DD"
        start_time_str = slot_data["startTime"]  # "HH:MM"
        end_time_str = slot_data["endTime"]  # "HH:MM"

        # Get care provider profile
        user = db.query(User).filter(User.id == care_provider_id).first()
        if not user or user.role != UserRole.CARE_PROVIDER:
            return {"success": False, "message": "Care provider not found"}

        care_profile = db.query(CareProviderProfile).filter(
            CareProviderProfile.user_id == care_provider_id
        ).first()
        if not care_profile:
            return {"success": False, "message": "Care provider profile not found"}

        # Parse date and times
        slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))

        # Create datetime objects
        slot_start = datetime.combine(slot_date, time(start_hour, start_minute))
        slot_end = datetime.combine(slot_date, time(end_hour, end_minute))

        # Check for appointment conflicts
        conflicting_appointments = db.query(Appointment).filter(
            Appointment.care_provider_id == care_provider_id,
            Appointment.start_time < slot_end,
            Appointment.end_time > slot_start,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).all()

        if conflicting_appointments:
            # Generate suggested ranges
            suggested_ranges = generate_available_ranges(
                db, care_provider_id, slot_date, conflicting_appointments
            )

            return {
                "success": False,
                "message": f"Cannot create availability due to {len(conflicting_appointments)} appointment conflict(s)",
                "suggested_ranges": suggested_ranges
            }

        # Check for existing availability overlap
        overlapping = db.query(Availability).filter(
            Availability.care_provider_id == care_profile.id,
            Availability.start_time < slot_end,
            Availability.end_time > slot_start,
        ).first()

        if overlapping:
            return {"success": False, "message": "This time slot overlaps with an existing availability slot"}

        # Create availability slot
        availability = Availability(
            id=str(uuid.uuid4()),
            care_provider_id=care_profile.id,
            start_time=slot_start,
            end_time=slot_end,
            is_available=True
        )
        db.add(availability)
        db.commit()

        # Invalidate cache after availability creation
        invalidate_cache()

        return {"success": True, "message": "Availability slot created successfully"}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error creating availability slot: {str(e)}"}
