"""Create test data for the new clean architecture"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User, UserRole, CareProviderProfile, SpecialistType, Appointment, AppointmentStatus, Availability
from app.core.security import get_password_hash


def create_test_data():
    """Create test users and data"""
    db = SessionLocal()
    
    try:
        # Create test users
        
        # 1. Regular user
        user1 = User(
            email="user@example.com",
            name="John Doe",
            first_name="John",
            last_name="Doe",
            hashed_password=get_password_hash("password123"),
            role=UserRole.USER,
            is_active=True
        )
        db.add(user1)
        
        # 2. Care provider user
        care_provider_user = User(
            email="therapist@example.com",
            name="Dr. Sarah Smith",
            first_name="Sarah",
            last_name="Smith",
            hashed_password=get_password_hash("password123"),
            role=UserRole.CARE_PROVIDER,
            is_active=True
        )
        db.add(care_provider_user)
        
        # 3. Another care provider
        care_provider_user2 = User(
            email="counselor@example.com",
            name="Dr. Mike Johnson",
            first_name="Mike",
            last_name="Johnson",
            hashed_password=get_password_hash("password123"),
            role=UserRole.CARE_PROVIDER,
            is_active=True
        )
        db.add(care_provider_user2)
        
        # 4. Admin user
        admin_user = User(
            email="admin@example.com",
            name="Admin User",
            first_name="Admin",
            last_name="User",
            hashed_password=get_password_hash("password123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        
        db.commit()
        db.refresh(user1)
        db.refresh(care_provider_user)
        db.refresh(care_provider_user2)
        db.refresh(admin_user)
        
        # Create care provider profiles
        profile1 = CareProviderProfile(
            user_id=care_provider_user.id,
            specialty=SpecialistType.MENTAL,
            bio="Experienced mental health therapist specializing in anxiety and depression.",
            hourly_rate=15000,  # $150.00 in cents
            license_number="LIC123456",
            years_experience=8,
            education="PhD in Clinical Psychology, Harvard University",
            certifications="Licensed Clinical Social Worker (LCSW)",
            is_accepting_patients=True
        )
        db.add(profile1)
        
        profile2 = CareProviderProfile(
            user_id=care_provider_user2.id,
            specialty=SpecialistType.PHYSICAL,
            bio="Physical therapist specializing in sports injuries and rehabilitation.",
            hourly_rate=12000,  # $120.00 in cents
            license_number="PT789012",
            years_experience=5,
            education="Master's in Physical Therapy, UCLA",
            certifications="Licensed Physical Therapist (LPT)",
            is_accepting_patients=True
        )
        db.add(profile2)
        
        db.commit()
        db.refresh(profile1)
        db.refresh(profile2)
        
        # Create availability slots
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Availability for therapist
        availability1 = Availability(
            care_provider_id=profile1.id,
            start_time=tomorrow.replace(hour=9, minute=0, second=0, microsecond=0),
            end_time=tomorrow.replace(hour=17, minute=0, second=0, microsecond=0),
            is_available=True
        )
        db.add(availability1)
        
        # Availability for physical therapist
        availability2 = Availability(
            care_provider_id=profile2.id,
            start_time=tomorrow.replace(hour=8, minute=0, second=0, microsecond=0),
            end_time=tomorrow.replace(hour=16, minute=0, second=0, microsecond=0),
            is_available=True
        )
        db.add(availability2)
        
        # Create a test appointment
        appointment_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        appointment = Appointment(
            user_id=user1.id,
            care_provider_id=care_provider_user.id,
            start_time=appointment_time,
            end_time=appointment_time + timedelta(hours=1),
            status=AppointmentStatus.CONFIRMED,
            meeting_link="https://meet.example.com/test-meeting",
            notes="Initial consultation"
        )
        db.add(appointment)
        
        db.commit()
        
        print("✅ Test data created successfully!")
        print(f"👤 Regular user: {user1.email} (password: password123)")
        print(f"🩺 Care provider 1: {care_provider_user.email} (password: password123)")
        print(f"🏃 Care provider 2: {care_provider_user2.email} (password: password123)")
        print(f"👑 Admin: {admin_user.email} (password: password123)")
        print(f"📅 Created 1 test appointment")
        print(f"🕐 Created availability slots for tomorrow")
        
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_test_data()
