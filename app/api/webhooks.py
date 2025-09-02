"""Webhook handlers for external services"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.appointment_service import AppointmentService
from app.services.email_service import mailgun_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/mailgun", status_code=status.HTTP_200_OK)
async def mailgun_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """
    Handle Mailgun webhook events for email delivery tracking.
    
    Processes events like:
    - delivered: Email was successfully delivered
    - opened: Email was opened by recipient
    - clicked: Link in email was clicked
    - failed: Email delivery failed
    """
    try:
        # Get the raw body and form data
        body = await request.body()
        form_data = await request.form()
        
        # Extract webhook signature data
        token = form_data.get("token", "")
        timestamp = form_data.get("timestamp", "")
        signature = form_data.get("signature", "")
        
        # Verify webhook signature
        if not mailgun_service.verify_webhook_signature(token, timestamp, signature):
            logger.warning("Invalid Mailgun webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Extract event data
        event_type = form_data.get("event", "")
        message_id = form_data.get("Message-Id", "")
        recipient = form_data.get("recipient", "")
        
        logger.info(f"Received Mailgun webhook: {event_type} for message {message_id}")
        
        # Extract appointment ID from custom variables
        appointment_id = form_data.get("appointment_id", "")
        if not appointment_id:
            # Try to extract from custom variables (v:appointment_id)
            for key, value in form_data.items():
                if key.startswith("v:appointment_id"):
                    appointment_id = value
                    break
        
        if not appointment_id:
            logger.warning(f"No appointment ID found in webhook for message {message_id}")
            return {"status": "ignored", "reason": "no appointment ID"}
        
        # Process the event
        appointment_service = AppointmentService(db)
        
        if event_type in ["delivered", "opened"]:
            appointment_service.update_email_delivery_status(appointment_id, event_type)
            logger.info(f"Updated appointment {appointment_id} email status: {event_type}")
        elif event_type == "failed":
            logger.error(f"Email delivery failed for appointment {appointment_id}: {form_data.get('reason', 'Unknown')}")
        elif event_type == "clicked":
            logger.info(f"Email link clicked for appointment {appointment_id}")
        else:
            logger.info(f"Unhandled event type: {event_type}")
        
        return {"status": "processed", "event": event_type, "appointment_id": appointment_id}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing Mailgun webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )


@router.get("/mailgun/test", status_code=status.HTTP_200_OK)
def test_mailgun_webhook() -> Dict[str, str]:
    """
    Test endpoint to verify webhook configuration.
    This endpoint can be used to test that the webhook URL is accessible.
    """
    return {
        "status": "ok",
        "message": "Mailgun webhook endpoint is accessible",
        "configured": mailgun_service.is_configured()
    }
