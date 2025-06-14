"""API endpoints for personal journal entries created by care providers and admins"""

import os
import logging
from typing import Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.db.database import get_db
from app.db.models import PersonalJournal, PersonalJournalAttachment, User, UserRole, UserAssignment
from app.schemas.personal_journal import (
    PersonalJournal as PersonalJournalSchema,
    PersonalJournalCreate,
    PersonalJournalUpdate,
    PersonalJournalWithDetails,
    PersonalJournalAttachmentCreate,
    PersonalJournalAttachment as PersonalJournalAttachmentSchema,
    PersonalJournalStats,
    VoiceTranscriptionRequest,
    VoiceTranscriptionResponse,
)
from app.api.deps import get_current_user
from app.api.role_deps import require_care_or_admin
from app.services.voice_transcription import transcribe_voice_file

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_patient_access(db: Session, current_user: User, patient_id: str) -> User:
    """
    Check if the current user has access to create/view journals for the specified patient.
    Returns the patient user object if access is granted.
    """
    # Get the patient
    patient = db.query(User).filter(
        User.id == patient_id,
        User.role == UserRole.USER,
        User.is_active == True
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or not a regular user"
        )
    
    # Admins have access to all patients
    if current_user.role == UserRole.ADMIN:
        return patient
    
    # Care providers can only access assigned patients
    if current_user.role == UserRole.CARE_PROVIDER:
        assignment = db.query(UserAssignment).filter(
            UserAssignment.user_id == patient_id,
            UserAssignment.care_provider_id == current_user.id,
            UserAssignment.is_active == True
        ).first()
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You are not assigned to this patient."
            )
        
        return patient
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. Insufficient permissions."
    )


def _check_journal_access(db: Session, current_user: User, journal: PersonalJournal) -> bool:
    """
    Check if the current user has access to view/edit a specific journal entry.
    """
    # Author can always access their own entries
    if journal.author_id == current_user.id:
        return True
    
    # Admins can access all entries
    if current_user.role == UserRole.ADMIN:
        return True
    
    # Care providers can access shared entries for their assigned patients
    if current_user.role == UserRole.CARE_PROVIDER:
        # Check if user is assigned to the patient
        assignment = db.query(UserAssignment).filter(
            UserAssignment.user_id == journal.patient_id,
            UserAssignment.care_provider_id == current_user.id,
            UserAssignment.is_active == True
        ).first()
        
        if assignment and journal.is_shared:
            # Check if explicitly shared with this care provider
            if (journal.shared_with_care_providers and 
                current_user.id in journal.shared_with_care_providers):
                return True
            # If no specific sharing list, all care providers of the patient can view
            if not journal.shared_with_care_providers:
                return True
    
    return False


@router.get("/", response_model=List[PersonalJournalWithDetails])
def get_personal_journals(
    skip: int = 0,
    limit: int = 100,
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    author_id: Optional[str] = Query(None, description="Filter by author ID"),
    from_date: Optional[datetime] = Query(None, description="Filter entries from this date"),
    to_date: Optional[datetime] = Query(None, description="Filter entries to this date"),
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get personal journal entries with filtering options.
    - Admins: Can see all entries
    - Care providers: Can see their own entries and shared entries for assigned patients
    """
    query = db.query(PersonalJournal)
    
    # Apply role-based filtering
    if current_user.role == UserRole.CARE_PROVIDER:
        # Get assigned patient IDs
        assigned_patient_ids = [
            assignment.user_id for assignment in db.query(UserAssignment).filter(
                UserAssignment.care_provider_id == current_user.id,
                UserAssignment.is_active == True
            ).all()
        ]

        # Filter to own entries or shared entries for assigned patients
        query = query.filter(
            or_(
                PersonalJournal.author_id == current_user.id,
                and_(
                    PersonalJournal.patient_id.in_(assigned_patient_ids),
                    PersonalJournal.is_shared == True
                )
            )
        )
    
    # Apply additional filters
    if patient_id:
        # Verify access to this patient
        _check_patient_access(db, current_user, patient_id)
        query = query.filter(PersonalJournal.patient_id == patient_id)
    
    if author_id:
        query = query.filter(PersonalJournal.author_id == author_id)
    
    if from_date:
        query = query.filter(PersonalJournal.entry_datetime >= from_date)
    
    if to_date:
        query = query.filter(PersonalJournal.entry_datetime <= to_date)
    
    # Order by entry datetime (most recent first)
    query = query.order_by(desc(PersonalJournal.entry_datetime))
    
    journals = query.offset(skip).limit(limit).all()
    
    # Build response with additional details
    result = []
    for journal in journals:
        # Verify access to this specific journal
        if not _check_journal_access(db, current_user, journal):
            continue
            
        # Get patient and author details
        patient = db.query(User).filter(User.id == journal.patient_id).first()
        author = db.query(User).filter(User.id == journal.author_id).first()
        
        journal_dict = {
            **journal.__dict__,
            "patient_name": patient.name if patient else None,
            "patient_first_name": patient.first_name if patient else None,
            "patient_last_name": patient.last_name if patient else None,
            "patient_email": patient.email if patient else None,
            "patient_country": patient.country if patient else None,
            "author_name": author.name if author else None,
            "author_first_name": author.first_name if author else None,
            "author_last_name": author.last_name if author else None,
            "author_email": author.email if author else None,
        }
        result.append(journal_dict)
    
    return result


@router.post("/", response_model=PersonalJournalSchema, status_code=status.HTTP_201_CREATED)
def create_personal_journal(
    journal_in: PersonalJournalCreate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new personal journal entry.
    """
    # Verify access to the patient
    _check_patient_access(db, current_user, journal_in.patient_id)
    
    # Create the journal entry
    journal = PersonalJournal(
        patient_id=journal_in.patient_id,
        author_id=current_user.id,
        entry_datetime=journal_in.entry_datetime,
        title=journal_in.title,
        content=journal_in.content,
        is_shared=journal_in.is_shared or False,
        shared_with_care_providers=journal_in.shared_with_care_providers,
    )
    
    db.add(journal)
    db.commit()
    db.refresh(journal)
    
    # Add attachments if provided
    if journal_in.attachments:
        for attachment_data in journal_in.attachments:
            attachment = PersonalJournalAttachment(
                journal_id=journal.id,
                **attachment_data.model_dump()
            )
            db.add(attachment)
        
        db.commit()
        db.refresh(journal)
    
    return journal


@router.get("/{journal_id}", response_model=PersonalJournalSchema)
def get_personal_journal(
    journal_id: str,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific personal journal entry by ID.
    """
    journal = db.query(PersonalJournal).filter(PersonalJournal.id == journal_id).first()
    
    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found"
        )
    
    # Check access permissions
    if not _check_journal_access(db, current_user, journal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You don't have permission to view this journal entry."
        )
    
    return journal


@router.put("/{journal_id}", response_model=PersonalJournalSchema)
def update_personal_journal(
    journal_id: str,
    journal_in: PersonalJournalUpdate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a personal journal entry.
    Only the author or admin can update entries.
    """
    journal = db.query(PersonalJournal).filter(PersonalJournal.id == journal_id).first()
    
    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found"
        )
    
    # Only author or admin can update
    if journal.author_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only the author or admin can update this entry."
        )
    
    # Update fields
    update_data = journal_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(journal, field, value)
    
    db.commit()
    db.refresh(journal)
    
    return journal


@router.delete("/{journal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personal_journal(
    journal_id: str,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a personal journal entry.
    Only the author or admin can delete entries.
    """
    journal = db.query(PersonalJournal).filter(PersonalJournal.id == journal_id).first()
    
    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found"
        )
    
    # Only author or admin can delete
    if journal.author_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only the author or admin can delete this entry."
        )
    
    db.delete(journal)
    db.commit()


# Attachment endpoints
@router.post("/{journal_id}/attachments", response_model=PersonalJournalAttachmentSchema, status_code=status.HTTP_201_CREATED)
def add_journal_attachment(
    journal_id: str,
    attachment_in: PersonalJournalAttachmentCreate,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Add an attachment to a personal journal entry.
    """
    journal = db.query(PersonalJournal).filter(PersonalJournal.id == journal_id).first()

    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found"
        )

    # Only author or admin can add attachments
    if journal.author_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only the author or admin can add attachments."
        )

    attachment = PersonalJournalAttachment(
        journal_id=journal_id,
        **attachment_in.model_dump()
    )

    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment


@router.get("/{journal_id}/attachments", response_model=List[PersonalJournalAttachmentSchema])
def get_journal_attachments(
    journal_id: str,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all attachments for a personal journal entry.
    """
    journal = db.query(PersonalJournal).filter(PersonalJournal.id == journal_id).first()

    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found"
        )

    # Check access permissions
    if not _check_journal_access(db, current_user, journal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You don't have permission to view this journal entry."
        )

    attachments = db.query(PersonalJournalAttachment).filter(
        PersonalJournalAttachment.journal_id == journal_id
    ).all()

    return attachments


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal_attachment(
    attachment_id: str,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a journal attachment.
    """
    attachment = db.query(PersonalJournalAttachment).filter(
        PersonalJournalAttachment.id == attachment_id
    ).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found"
        )

    # Get the journal to check permissions
    journal = db.query(PersonalJournal).filter(
        PersonalJournal.id == attachment.journal_id
    ).first()

    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated journal entry not found"
        )

    # Only author or admin can delete attachments
    if journal.author_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only the author or admin can delete attachments."
        )

    db.delete(attachment)
    db.commit()


# Statistics endpoint
@router.get("/stats/overview", response_model=PersonalJournalStats)
def get_personal_journal_stats(
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get statistics about personal journal entries.
    """
    # Base query for accessible journals
    base_query = db.query(PersonalJournal)

    if current_user.role == UserRole.CARE_PROVIDER:
        # Get assigned patient IDs
        assigned_patient_ids = [
            assignment.user_id for assignment in db.query(UserAssignment).filter(
                UserAssignment.care_provider_id == current_user.id,
                UserAssignment.is_active == True
            ).all()
        ]

        # Filter to own entries or shared entries for assigned patients
        base_query = base_query.filter(
            or_(
                PersonalJournal.author_id == current_user.id,
                and_(
                    PersonalJournal.patient_id.in_(assigned_patient_ids),
                    PersonalJournal.is_shared == True
                )
            )
        )

    # Calculate statistics
    total_entries = base_query.count()

    # Entries this week
    week_ago = datetime.now() - timedelta(days=7)
    entries_this_week = base_query.filter(
        PersonalJournal.created_at >= week_ago
    ).count()

    # Entries this month
    month_ago = datetime.now() - timedelta(days=30)
    entries_this_month = base_query.filter(
        PersonalJournal.created_at >= month_ago
    ).count()

    # Total patients with entries
    total_patients_with_entries = base_query.distinct(PersonalJournal.patient_id).count()

    # Most active author (for admins) or current user stats (for care providers)
    most_active_author = None
    if current_user.role == UserRole.ADMIN:
        author_stats = db.query(
            PersonalJournal.author_id,
            func.count(PersonalJournal.id).label('entry_count')
        ).group_by(PersonalJournal.author_id).order_by(
            func.count(PersonalJournal.id).desc()
        ).first()

        if author_stats:
            author = db.query(User).filter(User.id == author_stats.author_id).first()
            most_active_author = f"{author.first_name} {author.last_name}" if author else "Unknown"

    # Most documented patient
    patient_stats = base_query.with_entities(
        PersonalJournal.patient_id,
        func.count(PersonalJournal.id).label('entry_count')
    ).group_by(PersonalJournal.patient_id).order_by(
        func.count(PersonalJournal.id).desc()
    ).first()

    most_documented_patient = None
    if patient_stats:
        patient = db.query(User).filter(User.id == patient_stats.patient_id).first()
        most_documented_patient = f"{patient.first_name} {patient.last_name}" if patient else "Unknown"

    return PersonalJournalStats(
        total_entries=total_entries,
        entries_this_week=entries_this_week,
        entries_this_month=entries_this_month,
        total_patients_with_entries=total_patients_with_entries,
        most_active_author=most_active_author,
        most_documented_patient=most_documented_patient,
    )


# Voice transcription endpoint
@router.post("/transcribe-voice", response_model=VoiceTranscriptionResponse)
def transcribe_voice_recording(
    transcription_request: VoiceTranscriptionRequest,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Transcribe a voice recording to text.
    """
    file_path = transcription_request.file_path
    language = transcription_request.language or "en"

    # Verify file exists and is accessible
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice file not found"
        )

    try:
        # Transcribe the voice file
        transcription, confidence, duration = transcribe_voice_file(file_path, language)

        if transcription is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to transcribe voice file. Please check the file format and try again."
            )

        return VoiceTranscriptionResponse(
            transcription=transcription,
            confidence=confidence,
            duration_seconds=duration
        )

    except Exception as e:
        logger.error(f"Error transcribing voice file {file_path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while transcribing the voice file"
        )
