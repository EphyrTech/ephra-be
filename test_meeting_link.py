#!/usr/bin/env python3
"""
Test script to verify that care providers can add custom meeting links to appointments.
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000"
CARE_PROVIDER_EMAIL = "therapist@example.com"
CARE_PROVIDER_PASSWORD = "password123"
USER_EMAIL = "user@example.com"

def login_user(email: str, password: str) -> str:
    """Login and return access token"""
    response = requests.post(
        f"{BASE_URL}/v1/auth/login",
        data={
            "username": email,
            "password": password
        }
    )

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
        return None

def get_user_id(email: str, token: str) -> str:
    """Get user ID by email"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/v1/users/", headers=headers)

    if response.status_code == 200:
        users = response.json()
        for user in users:
            if user.get("email") == email:
                return user["id"]

    print(f"❌ Could not find user with email {email}")
    return None

def test_custom_meeting_link():
    """Test that care providers can add custom meeting links"""
    print("🧪 Testing custom meeting link functionality...")

    # Login as care provider
    print(f"🔐 Logging in as care provider: {CARE_PROVIDER_EMAIL}")
    care_provider_token = login_user(CARE_PROVIDER_EMAIL, CARE_PROVIDER_PASSWORD)
    if not care_provider_token:
        return False

    print("✅ Care provider login successful")

    # Get user ID
    print(f"👤 Getting user ID for: {USER_EMAIL}")
    user_id = get_user_id(USER_EMAIL, care_provider_token)
    if not user_id:
        return False

    print(f"✅ Found user ID: {user_id}")

    # Test 1: Create appointment with custom meeting link
    print("\n📅 Test 1: Creating appointment with custom meeting link...")

    start_time = datetime.now() + timedelta(days=1, hours=10)
    end_time = start_time + timedelta(hours=1)
    custom_meeting_link = "https://zoom.us/j/123456789"

    appointment_data = {
        "user_id": user_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "meeting_link": custom_meeting_link
    }

    headers = {"Authorization": f"Bearer {care_provider_token}"}
    response = requests.post(
        f"{BASE_URL}/v1/appointments/",
        json=appointment_data,
        headers=headers
    )

    if response.status_code == 201:
        appointment = response.json()
        if appointment.get("meeting_link") == custom_meeting_link:
            print("✅ Custom meeting link saved successfully!")
            print(f"   Meeting link: {appointment['meeting_link']}")
            appointment_id_1 = appointment["id"]
        else:
            print(f"❌ Meeting link mismatch. Expected: {custom_meeting_link}, Got: {appointment.get('meeting_link')}")
            return False
    else:
        print(f"❌ Failed to create appointment: {response.status_code} - {response.text}")
        return False

    # Test 2: Create appointment without meeting link (should auto-generate)
    print("\n📅 Test 2: Creating appointment without meeting link...")

    start_time_2 = datetime.now() + timedelta(days=1, hours=14)
    end_time_2 = start_time_2 + timedelta(hours=1)

    appointment_data_2 = {
        "user_id": user_id,
        "start_time": start_time_2.isoformat(),
        "end_time": end_time_2.isoformat()
        # No meeting_link provided
    }

    response = requests.post(
        f"{BASE_URL}/v1/appointments/",
        json=appointment_data_2,
        headers=headers
    )

    if response.status_code == 201:
        appointment = response.json()
        meeting_link = appointment.get("meeting_link")
        if meeting_link and meeting_link.startswith("https://meet.example.com/"):
            print("✅ Auto-generated meeting link created successfully!")
            print(f"   Meeting link: {meeting_link}")
            appointment_id_2 = appointment["id"]
        else:
            print(f"❌ Auto-generated meeting link invalid: {meeting_link}")
            return False
    else:
        print(f"❌ Failed to create appointment: {response.status_code} - {response.text}")
        return False

    # Test 3: Verify appointments can be retrieved with meeting links
    print("\n📋 Test 3: Retrieving appointments to verify meeting links...")

    response = requests.get(f"{BASE_URL}/v1/appointments/", headers=headers)

    if response.status_code == 200:
        appointments = response.json()
        found_custom = False
        found_auto = False

        for appointment in appointments:
            if appointment["id"] == appointment_id_1:
                if appointment.get("meeting_link") == custom_meeting_link:
                    found_custom = True
                    print(f"✅ Custom meeting link verified: {appointment['meeting_link']}")
            elif appointment["id"] == appointment_id_2:
                if appointment.get("meeting_link", "").startswith("https://meet.example.com/"):
                    found_auto = True
                    print(f"✅ Auto-generated meeting link verified: {appointment['meeting_link']}")

        if found_custom and found_auto:
            print("\n🎉 All tests passed! Meeting link functionality is working correctly.")
            return True
        else:
            print(f"❌ Could not verify appointments. Custom found: {found_custom}, Auto found: {found_auto}")
            return False
    else:
        print(f"❌ Failed to retrieve appointments: {response.status_code} - {response.text}")
        return False

if __name__ == "__main__":
    print("🚀 Starting meeting link functionality test...\n")

    try:
        success = test_custom_meeting_link()
        if success:
            print("\n✅ All tests completed successfully!")
        else:
            print("\n❌ Some tests failed!")
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
