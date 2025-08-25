"""Tests for care provider service"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.care_provider_service import CareProviderService
from app.services.exceptions import (
    ValidationError,
    NotFoundError,
    PermissionError,
    ConflictError,
    BusinessRuleError,
)
from app.db.models import User, UserRole, CareProviderProfile, SpecialistType, Availability
from app.schemas.care_provider import (
    CareProviderProfileCreate,
    CareProviderProfileUpdate,
    AvailabilityCreate,
    AvailabilityUpdate,
)


class TestCareProviderService:
    """Test cases for CareProviderService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        """CareProviderService instance with mocked database"""
        return CareProviderService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Mock care provider user"""
        user = Mock(spec=User)
        user.id = "user-123"
        user.role = UserRole.CARE_PROVIDER
        user.is_active = True
        return user

    @pytest.fixture
    def mock_profile(self, mock_user):
        """Mock care provider profile"""
        profile = Mock(spec=CareProviderProfile)
        profile.id = "profile-123"
        profile.user_id = "user-123"
        profile.specialty = SpecialistType.MENTAL
        profile.is_accepting_patients = True
        profile.user = mock_user
        return profile

    def test_get_care_providers_success(self, service, mock_db, mock_profile):
        """Test successful retrieval of care providers"""
        # Setup
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_profile]

        # Execute
        result = service.get_care_providers()

        # Assert
        assert len(result) == 1
        assert result[0]["user_name"] == mock_profile.user.name
        mock_db.query.assert_called_once()

    def test_get_care_providers_with_specialty_filter(self, service, mock_db, mock_profile):
        """Test care provider retrieval with specialty filter"""
        # Setup
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_profile]

        # Execute
        result = service.get_care_providers(specialty="mental")

        # Assert
        assert len(result) == 1
        # Verify specialty filter was applied
        assert mock_query.filter.call_count >= 2  # Base filters + specialty filter

    def test_get_care_providers_invalid_specialty(self, service, mock_db):
        """Test care provider retrieval with invalid specialty"""
        with pytest.raises(ValidationError) as exc_info:
            service.get_care_providers(specialty="invalid")
        
        assert "Invalid specialty" in str(exc_info.value)

    def test_get_care_providers_invalid_pagination(self, service, mock_db):
        """Test care provider retrieval with invalid pagination"""
        # Test negative skip
        with pytest.raises(ValidationError) as exc_info:
            service.get_care_providers(skip=-1)
        assert "Skip parameter must be non-negative" in str(exc_info.value)

        # Test invalid limit
        with pytest.raises(ValidationError) as exc_info:
            service.get_care_providers(limit=0)
        assert "Limit must be between 1 and 1000" in str(exc_info.value)

        # Test limit too high
        with pytest.raises(ValidationError) as exc_info:
            service.get_care_providers(limit=1001)
        assert "Limit must be between 1 and 1000" in str(exc_info.value)

    def test_get_my_profile_success(self, service, mock_db, mock_user, mock_profile):
        """Test successful retrieval of own profile"""
        # Setup
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_profile

        # Execute
        result = service.get_my_profile(mock_user)

        # Assert
        assert result == mock_profile
        mock_db.query.assert_called_once()

    def test_get_my_profile_not_care_provider(self, service, mock_db):
        """Test get_my_profile with non-care provider user"""
        # Setup
        user = Mock(spec=User)
        user.role = UserRole.USER

        # Execute & Assert
        with pytest.raises(PermissionError) as exc_info:
            service.get_my_profile(user)
        assert "Only care providers can access this resource" in str(exc_info.value)

    def test_get_my_profile_not_found(self, service, mock_db, mock_user):
        """Test get_my_profile when profile doesn't exist"""
        # Setup
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Execute & Assert
        with pytest.raises(NotFoundError) as exc_info:
            service.get_my_profile(mock_user)
        assert "Care provider profile not found" in str(exc_info.value)

    def test_create_my_profile_success(self, service, mock_db, mock_user):
        """Test successful profile creation"""
        # Setup
        profile_data = CareProviderProfileCreate(
            specialty=SpecialistType.MENTAL,
            bio="Test bio",
            hourly_rate=10000,
        )
        
        # Mock existing profile check
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # No existing profile

        # Execute
        result = service.create_my_profile(profile_data, mock_user)

        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_create_my_profile_already_exists(self, service, mock_db, mock_user, mock_profile):
        """Test profile creation when profile already exists"""
        # Setup
        profile_data = CareProviderProfileCreate(
            specialty=SpecialistType.MENTAL,
            bio="Test bio",
        )
        
        # Mock existing profile check
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_profile  # Existing profile

        # Execute & Assert
        with pytest.raises(ConflictError) as exc_info:
            service.create_my_profile(profile_data, mock_user)
        assert "Care provider profile already exists" in str(exc_info.value)

    def test_create_availability_success(self, service, mock_db, mock_user, mock_profile):
        """Test successful availability creation"""
        # Setup
        availability_data = AvailabilityCreate(
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=2),
        )
        
        # Mock profile retrieval
        with patch.object(service, 'get_my_profile', return_value=mock_profile):
            # Mock overlap check
            with patch.object(service, '_check_availability_overlap', return_value=False):
                # Execute
                result = service.create_my_availability(availability_data, mock_user)

                # Assert
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()
                mock_db.refresh.assert_called_once()

    def test_create_availability_invalid_time_range(self, service, mock_db, mock_user, mock_profile):
        """Test availability creation with invalid time range"""
        # Setup
        now = datetime.now()
        availability_data = AvailabilityCreate(
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=1),  # End before start
        )
        
        # Mock profile retrieval
        with patch.object(service, 'get_my_profile', return_value=mock_profile):
            # Execute & Assert
            with pytest.raises(ValidationError) as exc_info:
                service.create_my_availability(availability_data, mock_user)
            assert "Start time must be before end time" in str(exc_info.value)

    def test_create_availability_overlap(self, service, mock_db, mock_user, mock_profile):
        """Test availability creation with time overlap"""
        # Setup
        availability_data = AvailabilityCreate(
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=2),
        )
        
        # Mock profile retrieval
        with patch.object(service, 'get_my_profile', return_value=mock_profile):
            # Mock overlap check to return True
            with patch.object(service, '_check_availability_overlap', return_value=True):
                # Execute & Assert
                with pytest.raises(ConflictError) as exc_info:
                    service.create_my_availability(availability_data, mock_user)
                assert "This time slot overlaps with an existing availability slot" in str(exc_info.value)

    def test_delete_availability_with_appointments(self, service, mock_db, mock_user, mock_profile):
        """Test availability deletion when appointments exist"""
        # Setup
        availability_id = "avail-123"
        mock_availability = Mock()
        
        # Mock profile and availability retrieval
        with patch.object(service, 'get_my_profile', return_value=mock_profile):
            with patch.object(service, '_get_availability_by_id', return_value=mock_availability):
                # Mock conflicting appointments query
                mock_query = Mock()
                mock_db.query.return_value = mock_query
                mock_query.filter.return_value = mock_query
                mock_query.first.return_value = Mock()  # Conflicting appointment exists

                # Execute & Assert
                with pytest.raises(BusinessRuleError) as exc_info:
                    service.delete_my_availability(availability_id, mock_user)
                assert "Cannot delete availability slot with scheduled appointments" in str(exc_info.value)

    def test_ensure_care_provider_role_success(self, service, mock_user):
        """Test role validation for care provider"""
        # Should not raise exception
        service._ensure_care_provider_role(mock_user)

    def test_ensure_care_provider_role_failure(self, service):
        """Test role validation for non-care provider"""
        user = Mock(spec=User)
        user.role = UserRole.USER

        with pytest.raises(PermissionError) as exc_info:
            service._ensure_care_provider_role(user)
        assert "Only care providers can access this resource" in str(exc_info.value)

    def test_transform_profile_with_user(self, service, mock_profile):
        """Test profile transformation with user data"""
        result = service._transform_profile_with_user(mock_profile)
        
        assert "user_name" in result
        assert "user_email" in result
        assert "user_first_name" in result
        assert "user_last_name" in result
        assert result["user_name"] == mock_profile.user.name
