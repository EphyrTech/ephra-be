"""Test script to verify appointments API with user names"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/v1"

def test_appointments_with_user_names():
    """Test that appointments endpoint returns user names"""
    
    # First, login as care provider
    login_data = {
        "username": "therapist@example.com",
        "password": "password123"
    }
    
    print("🔐 Logging in as care provider...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return
    
    token_data = login_response.json()
    access_token = token_data.get("access_token")
    
    if not access_token:
        print("❌ No access token received")
        return
    
    print("✅ Login successful!")
    
    # Now get appointments
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print("📅 Fetching appointments...")
    appointments_response = requests.get(
        f"{BASE_URL}/appointments/",
        headers=headers
    )
    
    if appointments_response.status_code != 200:
        print(f"❌ Failed to get appointments: {appointments_response.status_code}")
        print(f"Response: {appointments_response.text}")
        return
    
    appointments = appointments_response.json()
    print(f"✅ Got {len(appointments)} appointments")
    
    # Check if appointments have user names
    for i, appointment in enumerate(appointments):
        print(f"\n📋 Appointment {i+1}:")
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

if __name__ == "__main__":
    test_appointments_with_user_names()
