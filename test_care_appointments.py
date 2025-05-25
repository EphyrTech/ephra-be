#!/usr/bin/env python3
"""
Test script to demonstrate care provider appointment creation functionality.
Run this after starting the FastAPI server and having care providers set up.
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/v1"

def test_care_provider_workflow():
    """Test the complete care provider workflow"""
    print("=== Care Provider Appointment Creation Test ===\n")
    
    # Step 1: Register a regular user
    print("1. Registering a regular user...")
    user_data = {
        "email": "patient@example.com",
        "password": "password123",
        "name": "John Patient",
        "first_name": "John",
        "last_name": "Patient"
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=user_data)
    if response.status_code == 201:
        patient = response.json()
        print(f"✅ Patient registered: {patient['email']}")
        patient_id = patient['id']
    else:
        print(f"❌ Patient registration failed: {response.text}")
        return
    
    # Step 2: Register a care provider (will need admin to assign role)
    print("\n2. Registering a care provider...")
    care_data = {
        "email": "therapist@example.com",
        "password": "password123",
        "name": "Dr. Sarah Therapist",
        "first_name": "Sarah",
        "last_name": "Therapist"
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=care_data)
    if response.status_code == 201:
        care_provider = response.json()
        print(f"✅ Care provider registered: {care_provider['email']}")
        care_provider_id = care_provider['id']
    else:
        print(f"❌ Care provider registration failed: {response.text}")
        return
    
    print("\n⚠️  Note: You need to manually assign CARE role to the therapist using admin endpoints:")
    print(f"   PUT /v1/admin/users/{care_provider_id}/role")
    print("   Body: {\"role\": \"CARE\", \"specialty\": \"MENTAL\"}")
    
    # Step 3: Login as care provider (assuming role has been assigned)
    print("\n3. Logging in as care provider...")
    login_data = {
        "email": "therapist@example.com",
        "password": "password123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        token_data = response.json()
        care_token = token_data['access_token']
        print("✅ Care provider logged in successfully")
    else:
        print(f"❌ Care provider login failed: {response.text}")
        return
    
    # Step 4: Get assigned users
    print("\n4. Getting assigned users...")
    headers = {"Authorization": f"Bearer {care_token}"}
    response = requests.get(f"{BASE_URL}/appointments/assigned-users", headers=headers)
    
    if response.status_code == 200:
        users = response.json()
        print(f"✅ Found {len(users)} users available for appointments")
        for user in users[:3]:  # Show first 3
            print(f"   - {user['name']} ({user['email']})")
    else:
        print(f"❌ Failed to get assigned users: {response.text}")
        if response.status_code == 403:
            print("   This likely means the user doesn't have CARE role assigned yet")
        return
    
    # Step 5: Create appointment for patient
    print("\n5. Creating appointment for patient...")
    
    # Schedule appointment for tomorrow at 2 PM
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    appointment_data = {
        "user_id": patient_id,  # Required for care providers
        "specialist_id": care_provider_id,  # Will be overridden to current user for care providers
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }
    
    response = requests.post(f"{BASE_URL}/appointments", json=appointment_data, headers=headers)
    
    if response.status_code == 201:
        appointment = response.json()
        print("✅ Appointment created successfully!")
        print(f"   Appointment ID: {appointment['id']}")
        print(f"   Patient: {patient_id}")
        print(f"   Care Provider: {appointment['specialist_id']}")
        print(f"   Time: {appointment['start_time']} - {appointment['end_time']}")
    else:
        print(f"❌ Failed to create appointment: {response.text}")
        return
    
    # Step 6: View care provider's appointments
    print("\n6. Viewing care provider's appointments...")
    response = requests.get(f"{BASE_URL}/appointments", headers=headers)
    
    if response.status_code == 200:
        appointments = response.json()
        print(f"✅ Care provider has {len(appointments)} appointments")
        for apt in appointments:
            print(f"   - {apt['start_time']} with user {apt['user_id']}")
    else:
        print(f"❌ Failed to get appointments: {response.text}")
    
    print("\n=== Test Summary ===")
    print("✅ Care provider appointment creation workflow tested!")
    print("\nKey Features Demonstrated:")
    print("- Care providers can view assigned users")
    print("- Care providers can create appointments for users")
    print("- Care providers see appointments where they are the specialist")
    print("- Role-based access control is enforced")

def test_admin_role_assignment():
    """Helper function to show admin role assignment"""
    print("\n=== Admin Role Assignment Example ===")
    print("To assign CARE role to a user, use admin endpoints:")
    print()
    print("1. Login as admin:")
    print("   POST /v1/auth/login")
    print("   Body: {\"email\": \"admin@example.com\", \"password\": \"admin_password\"}")
    print()
    print("2. Assign CARE role:")
    print("   PUT /v1/admin/users/{user_id}/role")
    print("   Headers: Authorization: Bearer {admin_token}")
    print("   Body: {\"role\": \"CARE\", \"specialty\": \"MENTAL\"}")
    print()
    print("3. Verify assignment:")
    print("   GET /v1/admin/care-providers")
    print("   Headers: Authorization: Bearer {admin_token}")

if __name__ == "__main__":
    test_care_provider_workflow()
    test_admin_role_assignment()
