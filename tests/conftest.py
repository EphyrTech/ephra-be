import os
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta

from app.db.database import Base, get_db
from app.db.models import User, Journal, Specialist, Appointment, MediaFile, Availability
from app.core.security import get_password_hash, create_access_token
from app.core.config import settings
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
def authorized_client(client, test_user_token):
    # Create a client with authorization headers
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {test_user_token}"
    }
    return client


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
def test_specialist(db):
    # Create a test specialist
    specialist = Specialist(
        name="Test Specialist",
        email="specialist@example.com",
        specialist_type="mental",
        bio="Test specialist bio",
        hourly_rate=10000,  # $100.00
    )
    db.add(specialist)
    db.commit()
    db.refresh(specialist)
    return specialist


@pytest.fixture(scope="function")
def test_availability(db, test_specialist):
    # Create test availability for the specialist
    now = datetime.now(tz=datetime.timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(hours=2)

    availability = Availability(
        specialist_id=test_specialist.id,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(availability)
    db.commit()
    db.refresh(availability)
    return availability


@pytest.fixture(scope="function")
def test_appointment(db, test_user, test_specialist):
    # Create a test appointment
    now = datetime.now(tz=datetime.timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)

    appointment = Appointment(
        user_id=test_user.id,
        specialist_id=test_specialist.id,
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
def admin_client(client, admin_token):
    # Create a client with admin authorization headers
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {admin_token}"
    }
    return client


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
        "content_type": "text/plain"
    }


@pytest.fixture(params=[
    {"skip": 0, "limit": 5},
    {"skip": 5, "limit": 5},
    {"skip": 0, "limit": 10},
    {"skip": 10, "limit": 10},
])
def pagination_params(request):
    # Parameterized fixture for testing pagination
    return request.param


@pytest.fixture(params=[
    {"query": "test"},
    {"query": "journal"},
    {"query": "nonexistent"},
])
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
    monkeypatch.setattr("app.api.auth.verify_google_token", mock_verify_token, raising=False)


@pytest.fixture(scope="function")
def mock_email_service(monkeypatch):
    # Mock email service for password reset testing
    sent_emails = []

    def mock_send_email(to_email, subject, body):
        sent_emails.append({
            "to": to_email,
            "subject": subject,
            "body": body,
        })
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
def multiple_specialists(db):
    # Create multiple specialists for testing
    specialists = []
    specialist_types = ["mental", "physical"]

    for i in range(10):
        specialist = Specialist(
            name=f"Specialist {i}",
            email=f"specialist{i}@example.com",
            specialist_type=specialist_types[i % 2],
            bio=f"Bio for specialist {i}",
            hourly_rate=10000 + (i * 1000),  # Varying rates
        )
        db.add(specialist)
        specialists.append(specialist)

    db.commit()
    for specialist in specialists:
        db.refresh(specialist)
    return specialists


@pytest.fixture(scope="function")
def multiple_appointments(db, test_user, test_specialist):
    # Create multiple appointments for testing
    appointments = []
    now = datetime.now(tz=datetime.timezone.utc)

    for i in range(5):
        start_time = now + timedelta(days=i+1)
        end_time = start_time + timedelta(hours=1)

        appointment = Appointment(
            user_id=test_user.id,
            specialist_id=test_specialist.id,
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
