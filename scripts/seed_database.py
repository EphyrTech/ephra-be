#!/usr/bin/env python3
"""
Database seeding script for Ephra FastAPI backend.

This script creates initial users with different roles:
- Admin user
- Care provider users (mental health and physical therapy)
- Regular users

Usage:
    python scripts/seed_database.py

Or in Docker:
    docker compose exec api uv run python scripts/seed_database.py
"""

import sys
import os
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Default credentials (can be overridden by environment variables)
DEFAULT_CREDENTIALS = {
    "admin_email": "admin@ephra.com",
    "admin_password": "admin123",
    "care_provider_password": "care123",
    "user_password": "user123"
}

from app.db.database import SessionLocal
from app.db.models import (
    User, UserRole, CareProviderProfile, SpecialistType,
    Appointment, AppointmentStatus, Availability, Journal
)
from app.core.security import get_password_hash


def get_credentials():
    """Get credentials from environment variables or use defaults."""
    return {
        "admin_email": os.getenv("SEED_ADMIN_EMAIL", DEFAULT_CREDENTIALS["admin_email"]),
        "admin_password": os.getenv("SEED_ADMIN_PASSWORD", DEFAULT_CREDENTIALS["admin_password"]),
        "care_provider_password": os.getenv("SEED_CARE_PROVIDER_PASSWORD", DEFAULT_CREDENTIALS["care_provider_password"]),
        "user_password": os.getenv("SEED_USER_PASSWORD", DEFAULT_CREDENTIALS["user_password"])
    }


def check_existing_users(db: Session) -> bool:
    """Check if users already exist in the database."""
    user_count = db.query(User).count()
    return user_count > 0


def create_admin_user(db: Session, credentials: dict) -> User:
    """Create an admin user if it doesn't exist."""
    # Check if admin already exists
    existing_admin = db.query(User).filter(User.email == credentials["admin_email"]).first()
    if existing_admin:
        print(f"   Admin user {credentials['admin_email']} already exists, skipping...")
        return existing_admin

    admin = User(
        email=credentials["admin_email"],
        name="System Administrator",
        first_name="System",
        last_name="Administrator",
        display_name="Admin",
        hashed_password=get_password_hash(credentials["admin_password"]),
        role=UserRole.ADMIN,
        is_active=True,
        country="United States",
        date_of_birth=date(1985, 1, 15)
    )
    db.add(admin)
    return admin


def create_care_providers(db: Session, credentials: dict) -> list[User]:
    """Create care provider users with their profiles."""
    care_providers = []

    # Mental health therapist
    existing_therapist = db.query(User).filter(User.email == "dr.sarah@ephra.com").first()
    if existing_therapist:
        print("   Dr. Sarah (therapist) already exists, skipping...")
        care_providers.append(existing_therapist)
    else:
        therapist = User(
            email="dr.sarah@ephra.com",
            name="Dr. Sarah Johnson",
            first_name="Sarah",
            last_name="Johnson",
            display_name="Dr. Sarah",
            hashed_password=get_password_hash(credentials["care_provider_password"]),
            role=UserRole.CARE_PROVIDER,
            is_active=True,
            country="United States",
            phone_number="+1-555-0123",
            date_of_birth=date(1980, 3, 22)
        )
        db.add(therapist)
        care_providers.append(therapist)

    # Physical therapist
    existing_physio = db.query(User).filter(User.email == "dr.mike@ephra.com").first()
    if existing_physio:
        print("   Dr. Mike (physical therapist) already exists, skipping...")
        care_providers.append(existing_physio)
    else:
        physical_therapist = User(
            email="dr.mike@ephra.com",
            name="Dr. Michael Chen",
            first_name="Michael",
            last_name="Chen",
            display_name="Dr. Mike",
            hashed_password=get_password_hash(credentials["care_provider_password"]),
            role=UserRole.CARE_PROVIDER,
            is_active=True,
            country="Canada",
            phone_number="+1-555-0456",
            date_of_birth=date(1978, 7, 10)
        )
        db.add(physical_therapist)
        care_providers.append(physical_therapist)

    # Counselor
    existing_counselor = db.query(User).filter(User.email == "dr.emma@ephra.com").first()
    if existing_counselor:
        print("   Dr. Emma (counselor) already exists, skipping...")
        care_providers.append(existing_counselor)
    else:
        counselor = User(
            email="dr.emma@ephra.com",
            name="Dr. Emma Williams",
            first_name="Emma",
            last_name="Williams",
            display_name="Dr. Emma",
            hashed_password=get_password_hash(credentials["care_provider_password"]),
            role=UserRole.CARE_PROVIDER,
            is_active=True,
            country="United Kingdom",
            phone_number="+44-20-7946-0958",
            date_of_birth=date(1982, 11, 5)
        )
        db.add(counselor)
        care_providers.append(counselor)

    return care_providers


def create_care_provider_profiles(db: Session, care_providers: list[User]) -> list[CareProviderProfile]:
    """Create professional profiles for care providers."""
    profiles = []

    # Profile for therapist (mental health)
    existing_therapist_profile = db.query(CareProviderProfile).filter(CareProviderProfile.user_id == care_providers[0].id).first()
    if existing_therapist_profile:
        print("   Therapist profile already exists, skipping...")
        profiles.append(existing_therapist_profile)
    else:
        therapist_profile = CareProviderProfile(
            user_id=care_providers[0].id,
            specialty=SpecialistType.MENTAL,
            bio="Licensed clinical psychologist with 12+ years of experience specializing in anxiety, depression, and trauma therapy. I use evidence-based approaches including CBT and EMDR.",
            hourly_rate=18000,  # $180.00 in cents
            license_number="PSY-12345-CA",
            years_experience=12,
            education="PhD in Clinical Psychology, Stanford University; MA in Psychology, UCLA",
            certifications="Licensed Clinical Psychologist (LCP), Certified EMDR Therapist, CBT Specialist",
            is_accepting_patients=True
        )
        db.add(therapist_profile)
        profiles.append(therapist_profile)

    # Profile for physical therapist
    existing_physio_profile = db.query(CareProviderProfile).filter(CareProviderProfile.user_id == care_providers[1].id).first()
    if existing_physio_profile:
        print("   Physical therapist profile already exists, skipping...")
        profiles.append(existing_physio_profile)
    else:
        physio_profile = CareProviderProfile(
            user_id=care_providers[1].id,
            specialty=SpecialistType.PHYSICAL,
            bio="Experienced physical therapist specializing in sports injuries, post-surgical rehabilitation, and chronic pain management. Committed to helping patients regain mobility and strength.",
            hourly_rate=15000,  # $150.00 in cents
            license_number="PT-67890-ON",
            years_experience=10,
            education="Master of Physical Therapy, University of Toronto; Bachelor of Kinesiology, McMaster University",
            certifications="Registered Physiotherapist (RPT), Orthopedic Manual Therapy, Dry Needling Certified",
            is_accepting_patients=True
        )
        db.add(physio_profile)
        profiles.append(physio_profile)

    # Profile for counselor (mental health)
    existing_counselor_profile = db.query(CareProviderProfile).filter(CareProviderProfile.user_id == care_providers[2].id).first()
    if existing_counselor_profile:
        print("   Counselor profile already exists, skipping...")
        profiles.append(existing_counselor_profile)
    else:
        counselor_profile = CareProviderProfile(
            user_id=care_providers[2].id,
            specialty=SpecialistType.MENTAL,
            bio="Compassionate counselor specializing in relationship therapy, family counseling, and stress management. I provide a safe space for personal growth and healing.",
            hourly_rate=14000,  # $140.00 in cents
            license_number="LMFT-54321-UK",
            years_experience=8,
            education="Master of Counseling Psychology, University of Edinburgh; Bachelor of Psychology, Oxford University",
            certifications="Licensed Marriage and Family Therapist (LMFT), Certified Gottman Method Couples Therapist",
            is_accepting_patients=True
        )
        db.add(counselor_profile)
        profiles.append(counselor_profile)

    return profiles


def create_regular_users(db: Session, credentials: dict) -> list[User]:
    """Create regular users."""
    users = []

    # User 1 - Active user
    existing_user1 = db.query(User).filter(User.email == "john.doe@example.com").first()
    if existing_user1:
        print("   John Doe already exists, skipping...")
        users.append(existing_user1)
    else:
        user1 = User(
            email="john.doe@example.com",
            name="John Doe",
            first_name="John",
            last_name="Doe",
            display_name="John",
            hashed_password=get_password_hash(credentials["user_password"]),
            role=UserRole.USER,
            is_active=True,
            country="United States",
            phone_number="+1-555-0789",
            date_of_birth=date(1990, 5, 15)
        )
        db.add(user1)
        users.append(user1)

    # User 2 - Another active user
    existing_user2 = db.query(User).filter(User.email == "jane.smith@example.com").first()
    if existing_user2:
        print("   Jane Smith already exists, skipping...")
        users.append(existing_user2)
    else:
        user2 = User(
            email="jane.smith@example.com",
            name="Jane Smith",
            first_name="Jane",
            last_name="Smith",
            display_name="Jane",
            hashed_password=get_password_hash(credentials["user_password"]),
            role=UserRole.USER,
            is_active=True,
            country="Canada",
            phone_number="+1-555-0321",
            date_of_birth=date(1988, 9, 23)
        )
        db.add(user2)
        users.append(user2)

    # User 3 - Demo user
    existing_demo = db.query(User).filter(User.email == "demo@ephra.com").first()
    if existing_demo:
        print("   Demo user already exists, skipping...")
        users.append(existing_demo)
    else:
        demo_user = User(
            email="demo@ephra.com",
            name="Demo User",
            first_name="Demo",
            last_name="User",
            display_name="Demo",
            hashed_password=get_password_hash(credentials["user_password"]),
            role=UserRole.USER,
            is_active=True,
            country="United States",
            date_of_birth=date(1992, 12, 1)
        )
        db.add(demo_user)
        users.append(demo_user)

    return users


def create_sample_data(db: Session, users: list[User], care_providers: list[User], profiles: list[CareProviderProfile]):
    """Create sample appointments and availability."""
    # Create availability for next week
    next_week = datetime.now() + timedelta(days=7)

    # Availability for therapist
    availability1 = Availability(
        care_provider_id=profiles[0].id,
        start_time=next_week.replace(hour=9, minute=0, second=0, microsecond=0),
        end_time=next_week.replace(hour=17, minute=0, second=0, microsecond=0),
        is_available=True
    )
    db.add(availability1)

    # Availability for physical therapist
    availability2 = Availability(
        care_provider_id=profiles[1].id,
        start_time=next_week.replace(hour=8, minute=0, second=0, microsecond=0),
        end_time=next_week.replace(hour=16, minute=0, second=0, microsecond=0),
        is_available=True
    )
    db.add(availability2)

    # Sample appointment
    appointment_time = next_week.replace(hour=10, minute=0, second=0, microsecond=0)
    appointment = Appointment(
        user_id=users[0].id,
        care_provider_id=care_providers[0].id,
        start_time=appointment_time,
        end_time=appointment_time + timedelta(hours=1),
        status=AppointmentStatus.CONFIRMED,
        meeting_link="https://meet.ephra.com/session-123",
        notes="Initial consultation for anxiety management"
    )
    db.add(appointment)

    # Sample journal entry
    journal_entry = Journal(
        user_id=users[0].id,
        title="My First Journal Entry",
        content="Today was a good day. I felt more positive and managed my stress well.",
        mood="good",
        emotions=["happy", "calm", "optimistic"],
        sleep="good",
        quick_note="Feeling grateful today",
        notes="Had a productive therapy session. Practiced breathing exercises.",
        date=datetime.now(),
        shared_with_coach=False
    )
    db.add(journal_entry)


def seed_database():
    """Main seeding function."""
    print("🌱 Starting database seeding...")

    # Get credentials from environment variables
    credentials = get_credentials()

    db = SessionLocal()

    try:
        # Check if users already exist
        if check_existing_users(db):
            print("⚠️  Users already exist in the database.")
            # In production, skip the prompt and just continue
            if os.getenv("ENVIRONMENT") == "production":
                print("🔄 Production environment detected - continuing with seeding...")
            else:
                response = input("Do you want to continue and add more users? (y/N): ")
                if response.lower() != 'y':
                    print("❌ Seeding cancelled.")
                    return

        print("👑 Creating admin user...")
        admin = create_admin_user(db, credentials)

        print("🩺 Creating care providers...")
        care_providers = create_care_providers(db, credentials)

        # Commit users first to get their IDs
        db.commit()
        db.refresh(admin)
        for cp in care_providers:
            db.refresh(cp)

        print("📋 Creating care provider profiles...")
        profiles = create_care_provider_profiles(db, care_providers)

        print("👥 Creating regular users...")
        users = create_regular_users(db, credentials)

        # Commit all users and profiles
        db.commit()
        for user in users:
            db.refresh(user)
        for profile in profiles:
            db.refresh(profile)

        print("📅 Creating sample data...")
        create_sample_data(db, users, care_providers, profiles)

        # Final commit
        db.commit()

        print("\n✅ Database seeding completed successfully!")
        print("\n📊 Created accounts:")
        print(f"👑 Admin: {admin.email} (password: {credentials['admin_password']})")
        print(f"🩺 Therapist: {care_providers[0].email} (password: {credentials['care_provider_password']})")
        print(f"🏃 Physical Therapist: {care_providers[1].email} (password: {credentials['care_provider_password']})")
        print(f"💬 Counselor: {care_providers[2].email} (password: {credentials['care_provider_password']})")
        print(f"👤 User 1: {users[0].email} (password: {credentials['user_password']})")
        print(f"👤 User 2: {users[1].email} (password: {credentials['user_password']})")
        print(f"🎭 Demo User: {users[2].email} (password: {credentials['user_password']})")
        print("\n📝 Sample data:")
        print("• 1 sample appointment")
        print("• 1 sample journal entry")
        print("• Availability slots for care providers")

    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
