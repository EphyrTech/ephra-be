"""Test script to verify appointment service returns user names"""

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, UserRole
from app.services.appointment_service import AppointmentService

def test_appointment_service():
    """Test that appointment service returns user names"""
    
    db = SessionLocal()
    
    try:
        # Get a care provider user
        care_provider = db.query(User).filter(
            User.role == UserRole.CARE_PROVIDER,
            User.email == "therapist@example.com"
        ).first()
        
        if not care_provider:
            print("❌ Care provider not found")
            return
        
        print(f"✅ Found care provider: {care_provider.name}")
        
        # Test the appointment service
        appointment_service = AppointmentService(db)
        appointments = appointment_service.get_appointments_for_user(care_provider)
        
        print(f"📅 Found {len(appointments)} appointments")
        
        for i, appointment in enumerate(appointments):
            print(f"\n📋 Appointment {i+1}:")
            print(f"  Type: {type(appointment)}")
            
            if isinstance(appointment, dict):
                print(f"  ID: {appointment.get('id')}")
                print(f"  User ID: {appointment.get('user_id')}")
                print(f"  User Name: {appointment.get('user_name', 'NOT FOUND')}")
                print(f"  User Email: {appointment.get('user_email', 'NOT FOUND')}")
                print(f"  Care Provider Name: {appointment.get('care_provider_name', 'NOT FOUND')}")
                print(f"  Status: {appointment.get('status')}")
                print(f"  Start Time: {appointment.get('start_time')}")
                
                # Check if user_name is present
                if appointment.get('user_name'):
                    print("  ✅ User name is present!")
                else:
                    print("  ❌ User name is missing!")
            else:
                print(f"  ❌ Unexpected appointment type: {type(appointment)}")
                print(f"  Raw data: {appointment}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_appointment_service()
