"""Admin panel routes with Jinja2 templates and comprehensive logging"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

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
                           PersonalJournal, SpecialistType, User, UserRole)

logger = logging.getLogger(__name__)

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

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
    
    if not authenticate_superadmin(username, password):
        logger.warning(f"Failed admin login attempt - Username: {username}, IP: {ip_address}")
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Invalid credentials"
        }, status_code=401)
    
    # Create session
    session_id = create_admin_session(username, ip_address, user_agent)
    
    # Set secure cookie
    response = RedirectResponse(url="/admin-control-panel-x7k9m2/dashboard", status_code=302)
    response.set_cookie(
        key="admin_session_id",
        value=session_id,
        max_age=8 * 60 * 60,  # 8 hours
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict"
    )
    
    logger.info(f"Successful admin login - Username: {username}, IP: {ip_address}, Session: {session_id}")
    return response

@router.get("/logout")
async def admin_logout(
    request: Request,
    response: Response,
    session: AdminSession = Depends(require_admin_session)
):
    """Handle admin logout"""
    session_id = request.cookies.get("admin_session_id")
    if session_id:
        invalidate_admin_session(session_id)
    
    response = RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)
    response.delete_cookie("admin_session_id")
    
    log_admin_action(session, "LOGOUT")
    return response

@router.get("/session-info")
async def session_info(session: AdminSession = Depends(require_admin_session)):
    """Get current session info for AJAX checks"""
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
        "environment": settings.ENVIRONMENT,
        "database_status": "Connected",
        "active_admin_sessions": len(admin_sessions),
        "server_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "uptime": "N/A"  # Could be calculated if needed
    }
    
    # Chart data (last 7 days)
    chart_data = get_dashboard_chart_data(db)
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "session": session,
        "stats": stats,
        "recent_activity": activity_list,
        "system_info": system_info,
        "chart_data": chart_data
    })

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
    session: AdminSession = Depends(require_admin_session)
):
    """List active admin sessions"""
    log_admin_action(session, "VIEW_SESSIONS")
    
    return templates.TemplateResponse("admin/sessions.html", {
        "request": request,
        "session": session,
        "sessions": list(admin_sessions.values())
    })

@router.get("/audit-log", response_class=HTMLResponse)
async def admin_audit_log(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    page: int = 1,
    per_page: int = 50
):
    """Display audit log of admin actions"""
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

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """View user details"""
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
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Activate user"""
    log_admin_action(session, "ACTIVATE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    user.is_active = True
    db.commit()

    return {"success": True, "message": "User activated successfully"}

@router.post("/users/{user_id}/deactivate")
async def admin_deactivate_user(
    user_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Deactivate user"""
    log_admin_action(session, "DEACTIVATE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    user.is_active = False
    db.commit()

    return {"success": True, "message": "User deactivated successfully"}

@router.post("/users/{user_id}/delete")
async def admin_delete_user(
    user_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Delete user (soft delete by deactivating)"""
    log_admin_action(session, "DELETE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    # Soft delete by deactivating
    user.is_active = False
    db.commit()

    return {"success": True, "message": "User deleted successfully"}

@router.get("/journals", response_class=HTMLResponse)
async def admin_journals_list(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all journals"""
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
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all appointments"""
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
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all care providers"""
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
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all media files"""
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
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all personal journals"""
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
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all availability slots"""
    log_admin_action(session, "VIEW_AVAILABILITY", {"page": page})

    query = db.query(Availability).options(joinedload(Availability.care_provider)).order_by(desc(Availability.created_at))
    total = query.count()
    availability_slots = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/availability_list.html", {
        "request": request,
        "session": session,
        "availability_slots": availability_slots,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

# Additional CRUD endpoints for actions called by the UI

@router.post("/journals/{journal_id}/delete")
async def admin_delete_journal(
    journal_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Delete journal entry"""
    log_admin_action(session, "DELETE_JOURNAL", {"journal_id": journal_id})

    journal = db.query(Journal).filter(Journal.id == journal_id).first()
    if not journal:
        return {"success": False, "message": "Journal not found"}

    db.delete(journal)
    db.commit()

    return {"success": True, "message": "Journal deleted successfully"}

@router.post("/appointments/{appointment_id}/status")
async def admin_update_appointment_status(
    appointment_id: str,
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Update appointment status"""
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
        return {"success": True, "message": f"Appointment status updated to {new_status}"}
    except Exception as e:
        return {"success": False, "message": f"Error updating status: {str(e)}"}

@router.post("/appointments/{appointment_id}/delete")
async def admin_delete_appointment(
    appointment_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Delete appointment"""
    log_admin_action(session, "DELETE_APPOINTMENT", {"appointment_id": appointment_id})

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        return {"success": False, "message": "Appointment not found"}

    db.delete(appointment)
    db.commit()

    return {"success": True, "message": "Appointment deleted successfully"}

@router.post("/sessions/{session_id}/terminate")
async def admin_terminate_session(
    session_id: str,
    current_session: AdminSession = Depends(require_admin_session)
):
    """Terminate a specific admin session"""
    log_admin_action(current_session, "TERMINATE_SESSION", {"terminated_session_id": session_id})

    if invalidate_admin_session(session_id):
        return {"success": True, "message": "Session terminated successfully"}
    else:
        return {"success": False, "message": "Session not found or already terminated"}

@router.post("/sessions/terminate-others")
async def admin_terminate_other_sessions(
    current_session: AdminSession = Depends(require_admin_session)
):
    """Terminate all other admin sessions except current one"""
    terminated_count = 0
    sessions_to_terminate = []

    for session_id, session in admin_sessions.items():
        if session_id != current_session.session_id:
            sessions_to_terminate.append(session_id)

    for session_id in sessions_to_terminate:
        if invalidate_admin_session(session_id):
            terminated_count += 1

    log_admin_action(current_session, "TERMINATE_OTHER_SESSIONS", {
        "terminated_count": terminated_count
    })

    return {"success": True, "terminated_count": terminated_count}

@router.get("/audit-log/live")
async def admin_audit_log_live(
    session: AdminSession = Depends(require_admin_session)
):
    """Get live audit log entries for real-time monitoring"""
    from app.core.admin_auth import get_recent_audit_entries
    recent_entries = get_recent_audit_entries(10)
    return {"entries": recent_entries}

# Missing CRUD endpoints that templates are calling

@router.get("/users/create", response_class=HTMLResponse)
async def admin_user_create_form(
    request: Request,
    session: AdminSession = Depends(require_admin_session)
):
    """Show user creation form"""
    log_admin_action(session, "VIEW_USER_CREATE_FORM")
    return templates.TemplateResponse("admin/user_create.html", {
        "request": request,
        "session": session
    })

@router.post("/users/create")
async def admin_user_create(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Create a new user"""
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
            name=user_data.get("name"),
            phone_number=user_data.get("phone_number"),
            role=UserRole(user_data["role"]),
            is_active=user_data.get("is_active", True)
        )

        db.add(new_user)
        db.flush()  # Get the user ID

        # Create care provider profile if needed
        if user_data["role"] == "care_provider" and user_data.get("specialty"):
            care_profile = CareProviderProfile(
                id=str(uuid.uuid4()),
                user_id=new_user.id,
                specialty=SpecialistType(user_data["specialty"]),
                bio=user_data.get("bio"),
                hourly_rate=user_data.get("hourly_rate"),
                license_number=user_data.get("license_number")
            )
            db.add(care_profile)

        db.commit()

        return {"success": True, "message": "User created successfully", "user_id": new_user.id}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error creating user: {str(e)}"}

@router.get("/users/export")
async def admin_users_export(
    session: AdminSession = Depends(require_admin_session),
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
    session: AdminSession = Depends(require_admin_session),
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
    session: AdminSession = Depends(require_admin_session),
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
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Toggle availability slot status"""
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

    return {"success": True, "message": f"Availability slot {'enabled' if available else 'disabled'}"}

@router.post("/availability/{slot_id}/delete")
async def admin_delete_availability(
    slot_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Delete availability slot"""
    log_admin_action(session, "DELETE_AVAILABILITY", {"slot_id": slot_id})

    slot = db.query(Availability).filter(Availability.id == slot_id).first()
    if not slot:
        return {"success": False, "message": "Availability slot not found"}

    db.delete(slot)
    db.commit()

    return {"success": True, "message": "Availability slot deleted successfully"}

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

    slot = db.query(Availability).filter(Availability.id == slot_id).first()
    if not slot:
        return {"success": False, "message": "Availability slot not found"}

    db.delete(slot)
    db.commit()

    return {"success": True, "message": "Availability slot deleted successfully"}
