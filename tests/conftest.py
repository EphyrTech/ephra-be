import io
import os
from datetime import datetime, timedelta, timezone

# Set high rate limit for tests and disable cache
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["CACHE_TTL_SECONDS"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.database import Base, get_db
from app.db.models import (
    Appointment,
    Availability,
    CareProviderProfile,
    Journal,
    MediaFile,
    SpecialistType,
    User,
    UserRole,
)
from main import app

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    # Create the database and tables
    Base.metadata.create_all(bind=engine)

    # Create a new session for each test
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up after the test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    # Override the get_db dependency to use the test database
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    # Reset the dependency override
    app.dependency_overrides = {}


@pytest.fixture(scope="function")
def test_user(db):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password=hashed_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_user_token(test_user):
    # Create a token for the test user
    return create_access_token(subject=test_user.id)


@pytest.fixture(scope="function")
def authorized_client(client, test_user):
    # Override authentication dependencies to return the test user
    from app.api.deps import get_current_user_from_auth
    from app.core.auth_middleware import AuthInfo, verify_access_token

    def override_verify_access_token():
        return AuthInfo(
            sub=test_user.logto_user_id or f"test-{test_user.id}",
            aud=["test"],
            iss="test",
            exp=9999999999,
            iat=1000000000,
            scope="openid profile email",
        )

    def override_get_current_user_from_auth():
        return test_user

    app.dependency_overrides[verify_access_token] = override_verify_access_token
    app.dependency_overrides[get_current_user_from_auth] = (
        override_get_current_user_from_auth
    )

    yield client

    # Clean up overrides
    if verify_access_token in app.dependency_overrides:
        del app.dependency_overrides[verify_access_token]
    if get_current_user_from_auth in app.dependency_overrides:
        del app.dependency_overrides[get_current_user_from_auth]


@pytest.fixture(scope="function")
def test_journal(db, test_user):
    # Create a test journal entry
    journal = Journal(
        user_id=test_user.id,
        title="Test Journal",
        content="This is a test journal entry.",
    )
    db.add(journal)
    db.commit()
    db.refresh(journal)
    return journal


@pytest.fixture(scope="function")
def test_care_provider(db):
    # Create a test care provider user and profile
    hashed_password = get_password_hash("testpassword")
    user = User(
        email="careprovider@example.com",
        name="Test Care Provider",
        first_name="Test",
        last_name="Provider",
        hashed_password=hashed_password,
        role=UserRole.CARE_PROVIDER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create care provider profile
    profile = CareProviderProfile(
        user_id=user.id,
        specialty=SpecialistType.MENTAL,
        bio="Test care provider bio",
        hourly_rate=10000,  # $100.00
        license_number="TEST123",
        years_experience=5,
        education="Test University",
        certifications="Test Certification",
        is_accepting_patients=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return user, profile


@pytest.fixture(scope="function")
def test_specialist(test_care_provider):
    """Alias for test_care_provider for backward compatibility - returns just the profile"""
    user, profile = test_care_provider
    return profile


@pytest.fixture(scope="function")
def multiple_specialists(multiple_care_providers):
    """Alias for multiple_care_providers for backward compatibility"""
    return multiple_care_providers


@pytest.fixture(scope="function")
def test_availability(db, test_care_provider):
    # Create test availability for the care provider
    user, profile = test_care_provider
    now = datetime.now(tz=timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(hours=2)

    availability = Availability(
        care_provider_id=profile.id,
        start_time=start_time,
        end_time=end_time,
        is_available=True,
    )
    db.add(availability)
    db.commit()
    db.refresh(availability)
    return availability


@pytest.fixture(scope="function")
def test_appointment(db, test_user, test_care_provider):
    # Create a test appointment
    care_provider_user, profile = test_care_provider
    now = datetime.now(tz=timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)

    appointment = Appointment(
        user_id=test_user.id,
        care_provider_id=care_provider_user.id,
        start_time=start_time,
        end_time=end_time,
        status="pending",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@pytest.fixture(scope="function")
def test_media_file(db, test_user):
    # Create a test media file record
    media_file = MediaFile(
        user_id=test_user.id,
        filename="test.jpg",
        file_path="/tmp/test.jpg",
        file_type="image/jpeg",
        file_size=1024,
    )
    db.add(media_file)
    db.commit()
    db.refresh(media_file)
    return media_file


@pytest.fixture(scope="function")
def admin_user(db):
    # Create an admin user with additional privileges
    hashed_password = get_password_hash("adminpassword")
    user = User(
        email="admin@example.com",
        name="Admin User",
        hashed_password=hashed_password,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_token(admin_user):
    # Create a token for the admin user
    return create_access_token(subject=admin_user.id)


@pytest.fixture(scope="function")
def admin_client(client, admin_user):
    # Override authentication dependencies to return the admin user
    from app.api.deps import get_current_user_from_auth
    from app.core.auth_middleware import AuthInfo, verify_access_token

    def override_verify_access_token():
        return AuthInfo(
            sub=admin_user.logto_user_id or f"admin-{admin_user.id}",
            aud=["test"],
            iss="test",
            exp=9999999999,
            iat=1000000000,
            scope="openid profile email",
        )

    def override_get_current_user_from_auth():
        return admin_user

    app.dependency_overrides[verify_access_token] = override_verify_access_token
    app.dependency_overrides[get_current_user_from_auth] = (
        override_get_current_user_from_auth
    )

    yield client

    # Clean up overrides
    if verify_access_token in app.dependency_overrides:
        del app.dependency_overrides[verify_access_token]
    if get_current_user_from_auth in app.dependency_overrides:
        del app.dependency_overrides[get_current_user_from_auth]


@pytest.fixture(scope="function")
def care_provider_user(db):
    # Create a care provider user
    hashed_password = get_password_hash("carepassword")
    user = User(
        email="careprovider@example.com",
        name="Dr. Care Provider",
        first_name="Care",
        last_name="Provider",
        hashed_password=hashed_password,
        role=UserRole.CARE_PROVIDER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create care provider profile
    profile = CareProviderProfile(
        user_id=user.id,
        specialty=SpecialistType.MENTAL,
        bio="Test care provider for appointments",
        hourly_rate=15000,  # $150.00 in cents
        license_number="TEST123",
        years_experience=5,
        education="Test University",
        certifications="Test Certification",
        is_accepting_patients=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return user


@pytest.fixture(scope="function")
def care_provider_token(care_provider_user):
    # Create a token for the care provider user
    return create_access_token(subject=care_provider_user.id)


@pytest.fixture(scope="function")
def care_provider_client(client, care_provider_user):
    # Override authentication dependencies to return the care provider user
    from app.api.deps import get_current_user_from_auth
    from app.core.auth_middleware import AuthInfo, verify_access_token

    def override_verify_access_token():
        return AuthInfo(
            sub=care_provider_user.logto_user_id or f"care-{care_provider_user.id}",
            aud=["test"],
            iss="test",
            exp=9999999999,
            iat=1000000000,
            scope="openid profile email",
        )

    def override_get_current_user_from_auth():
        return care_provider_user

    app.dependency_overrides[verify_access_token] = override_verify_access_token
    app.dependency_overrides[get_current_user_from_auth] = (
        override_get_current_user_from_auth
    )

    yield client

    # Clean up overrides
    if verify_access_token in app.dependency_overrides:
        del app.dependency_overrides[verify_access_token]
    if get_current_user_from_auth in app.dependency_overrides:
        del app.dependency_overrides[get_current_user_from_auth]


@pytest.fixture(scope="function")
def inactive_user(db):
    # Create an inactive user for testing account status checks
    hashed_password = get_password_hash("inactivepassword")
    user = User(
        email="inactive@example.com",
        name="Inactive User",
        hashed_password=hashed_password,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def multiple_journals(db, test_user):
    # Create multiple journal entries for pagination testing
    journals = []
    for i in range(15):  # Create 15 journals
        journal = Journal(
            user_id=test_user.id,
            title=f"Test Journal {i}",
            content=f"This is test journal entry {i}.",
        )
        db.add(journal)
        journals.append(journal)

    db.commit()
    for journal in journals:
        db.refresh(journal)
    return journals


@pytest.fixture(scope="function")
def mock_file():
    # Create a mock file for upload testing
    file_content = b"test file content"
    file = io.BytesIO(file_content)
    return {
        "file": file,
        "size": len(file_content),
        "filename": "test_file.txt",
        "content_type": "text/plain",
    }


@pytest.fixture(
    params=[
        {"skip": 0, "limit": 5},
        {"skip": 5, "limit": 5},
        {"skip": 0, "limit": 10},
        {"skip": 10, "limit": 10},
    ]
)
def pagination_params(request):
    # Parameterized fixture for testing pagination
    return request.param


@pytest.fixture(
    params=[
        {"query": "test"},
        {"query": "journal"},
        {"query": "nonexistent"},
    ]
)
def search_query(request):
    # Parameterized fixture for testing search functionality
    return request.param


@pytest.fixture(scope="function")
def date_range():
    # Create a date range for filtering
    now = datetime.now(tz=datetime.timezone.utc)
    start_date = now - timedelta(days=7)
    end_date = now + timedelta(days=7)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


@pytest.fixture(scope="function")
def mock_google_auth(monkeypatch):
    # Mock Google authentication service
    def mock_verify_token(*args, **kwargs):
        return {
            "email": "google_user@example.com",
            "name": "Google User",
            "sub": "google_user_id",
        }

    # You would need to patch the actual function that verifies Google tokens
    # This is a placeholder - adjust the path to match your actual implementation
    monkeypatch.setattr(
        "app.api.auth.verify_google_token", mock_verify_token, raising=False
    )


@pytest.fixture(scope="function")
def mock_email_service(monkeypatch):
    # Mock email service for password reset testing
    sent_emails = []

    def mock_send_email(to_email, subject, body):
        sent_emails.append(
            {
                "to": to_email,
                "subject": subject,
                "body": body,
            }
        )
        return True

    # You would need to patch the actual function that sends emails
    # This is a placeholder - adjust the path to match your actual implementation
    monkeypatch.setattr("app.api.auth.send_email", mock_send_email, raising=False)
    return sent_emails


@pytest.fixture(scope="function")
def transactional_db(db):
    # Create a transaction that will be rolled back
    transaction = db.begin_nested()
    yield db
    transaction.rollback()


@pytest.fixture(scope="function")
def mock_env_vars(monkeypatch):
    # Mock environment variables for testing
    monkeypatch.setenv("TEST_MODE", "True")
    monkeypatch.setenv("TEST_SECRET_KEY", "test_secret_key")
    # Add more environment variables as needed


@pytest.fixture(scope="function")
def force_db_error(db, monkeypatch):
    # Force a database error for testing error handling
    def mock_commit(*args, **kwargs):
        raise Exception("Simulated database error")

    monkeypatch.setattr(db, "commit", mock_commit)


@pytest.fixture(scope="function")
def multiple_care_providers(db):
    # Create multiple care providers for testing
    care_providers = []
    specialist_types = [SpecialistType.MENTAL, SpecialistType.PHYSICAL]

    for i in range(10):
        # Create user
        hashed_password = get_password_hash("testpassword")
        user = User(
            email=f"careprovider{i}@example.com",
            name=f"Care Provider {i}",
            first_name=f"Provider{i}",
            last_name="Test",
            hashed_password=hashed_password,
            role=UserRole.CARE_PROVIDER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create profile
        profile = CareProviderProfile(
            user_id=user.id,
            specialty=specialist_types[i % 2],
            bio=f"Bio for care provider {i}",
            hourly_rate=10000 + (i * 1000),  # Varying rates
            license_number=f"LIC{i}",
            years_experience=i + 1,
            education="Test University",
            certifications="Test Certification",
            is_accepting_patients=True,
        )
        db.add(profile)
        care_providers.append((user, profile))

    db.commit()
    for user, profile in care_providers:
        db.refresh(profile)
    return care_providers


@pytest.fixture(scope="function")
def multiple_appointments(db, test_user, test_care_provider):
    # Create multiple appointments for testing
    care_provider_user, _ = test_care_provider
    appointments = []
    now = datetime.now(tz=datetime.timezone.utc)

    for i in range(5):
        start_time = now + timedelta(days=i + 1)
        end_time = start_time + timedelta(hours=1)

        appointment = Appointment(
            user_id=test_user.id,
            care_provider_id=care_provider_user.id,
            start_time=start_time,
            end_time=end_time,
            status="pending",
        )
        db.add(appointment)
        appointments.append(appointment)

    db.commit()
    for appointment in appointments:
        db.refresh(appointment)
    return appointments
