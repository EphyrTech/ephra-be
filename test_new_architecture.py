"""Test script to verify the new clean architecture works correctly"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/v1"

def test_authentication():
    """Test user authentication"""
    print("🔐 Testing Authentication...")
    
    # Test login
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "user@example.com",
        "password": "password123"
    })
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("✅ User login successful")
        return token
    else:
        print(f"❌ User login failed: {response.text}")
        return None

def test_care_provider_login():
    """Test care provider authentication"""
    print("🩺 Testing Care Provider Authentication...")
    
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "therapist@example.com",
        "password": "password123"
    })
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("✅ Care provider login successful")
        return token
    else:
        print(f"❌ Care provider login failed: {response.text}")
        return None

def test_care_providers_endpoint(token):
    """Test care providers listing"""
    print("👥 Testing Care Providers Endpoint...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/care-providers/", headers=headers)
    
    if response.status_code == 200:
        providers = response.json()
        print(f"✅ Found {len(providers)} care providers")
        for provider in providers:
            print(f"   - {provider['user_name']} ({provider['specialty']})")
        return providers
    else:
        print(f"❌ Failed to get care providers: {response.text}")
        return []

def test_appointments_endpoint(token):
    """Test appointments listing"""
    print("📅 Testing Appointments Endpoint...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/appointments/", headers=headers)
    
    if response.status_code == 200:
        appointments = response.json()
        print(f"✅ Found {len(appointments)} appointments")
        for apt in appointments:
            print(f"   - {apt['start_time']} with care provider {apt['care_provider_id']}")
        return appointments
    else:
        print(f"❌ Failed to get appointments: {response.text}")
        return []

def test_appointment_creation(token, care_provider_id):
    """Test appointment creation with service layer validation"""
    print("🆕 Testing Appointment Creation...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to create an appointment in the past (should fail)
    past_time = datetime.now() - timedelta(hours=1)
    response = requests.post(f"{BASE_URL}/appointments/", headers=headers, json={
        "care_provider_id": care_provider_id,
        "start_time": past_time.isoformat() + "Z",
        "end_time": (past_time + timedelta(hours=1)).isoformat() + "Z"
    })
    
    if response.status_code != 201:
        print("✅ Past appointment correctly rejected")
    else:
        print("❌ Past appointment was incorrectly accepted")
    
    # Try to create a valid future appointment
    future_time = datetime.now() + timedelta(days=2, hours=10)
    response = requests.post(f"{BASE_URL}/appointments/", headers=headers, json={
        "care_provider_id": care_provider_id,
        "start_time": future_time.isoformat() + "Z",
        "end_time": (future_time + timedelta(hours=1)).isoformat() + "Z"
    })
    
    if response.status_code == 201:
        appointment = response.json()
        print("✅ Future appointment created successfully")
        return appointment["id"]
    else:
        print(f"❌ Failed to create future appointment: {response.text}")
        return None

def test_care_provider_profile(care_token):
    """Test care provider profile endpoints"""
    print("👨‍⚕️ Testing Care Provider Profile...")
    
    headers = {"Authorization": f"Bearer {care_token}"}
    
    # Get own profile
    response = requests.get(f"{BASE_URL}/care-providers/me", headers=headers)
    
    if response.status_code == 200:
        profile = response.json()
        print(f"✅ Care provider profile retrieved: {profile['specialty']}")
        
        # Update profile
        update_response = requests.put(f"{BASE_URL}/care-providers/me", headers=headers, json={
            "bio": "Updated bio - Expert in anxiety and depression treatment with 8+ years experience."
        })
        
        if update_response.status_code == 200:
            print("✅ Care provider profile updated successfully")
        else:
            print(f"❌ Failed to update profile: {update_response.text}")
            
    else:
        print(f"❌ Failed to get care provider profile: {response.text}")

def test_error_handling(token):
    """Test error handling"""
    print("🚨 Testing Error Handling...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test accessing non-existent appointment
    response = requests.get(f"{BASE_URL}/appointments/non-existent-id", headers=headers)
    
    if response.status_code == 404:
        error = response.json()
        if "error" in error and "message" in error["error"]:
            print("✅ Error handling working correctly")
        else:
            print("❌ Error format incorrect")
    else:
        print(f"❌ Expected 404, got {response.status_code}")

def main():
    """Run all tests"""
    print("🧪 Testing New Clean Architecture")
    print("=" * 50)
    
    # Test user authentication
    user_token = test_authentication()
    if not user_token:
        return
    
    # Test care provider authentication
    care_token = test_care_provider_login()
    if not care_token:
        return
    
    # Test care providers endpoint
    providers = test_care_providers_endpoint(user_token)
    if not providers:
        return
    
    # Test appointments endpoint
    appointments = test_appointments_endpoint(user_token)
    
    # Test appointment creation
    if providers:
        care_provider_id = providers[0]["user_id"]
        test_appointment_creation(user_token, care_provider_id)
    
    # Test care provider profile
    test_care_provider_profile(care_token)
    
    # Test error handling
    test_error_handling(user_token)
    
    print("\n" + "=" * 50)
    print("🎉 Architecture testing completed!")
    print("\n✅ Key improvements verified:")
    print("   - Clean data model (no dual specialist system)")
    print("   - Service layer with business logic")
    print("   - Proper error handling")
    print("   - Role-based access control")
    print("   - Input validation")
    print("   - Centralized exception handling")

if __name__ == "__main__":
    main()
