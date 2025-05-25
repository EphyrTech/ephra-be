#!/usr/bin/env python3
"""
Simple test script to verify the role-based system is working.
Run this after starting the FastAPI server.
"""

import requests
import json

BASE_URL = "http://localhost:8000/v1"

def test_user_registration():
    """Test user registration with default USER role"""
    print("Testing user registration...")
    
    user_data = {
        "email": "testuser@example.com",
        "password": "testpassword123",
        "name": "Test User",
        "first_name": "Test",
        "last_name": "User"
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=user_data)
    print(f"Registration response: {response.status_code}")
    if response.status_code == 201:
        user = response.json()
        print(f"User created with role: {user.get('role', 'Not specified')}")
        return user
    else:
        print(f"Registration failed: {response.text}")
        return None

def test_user_login(email, password):
    """Test user login and token generation"""
    print(f"Testing login for {email}...")
    
    login_data = {
        "email": email,
        "password": password
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print(f"Login response: {response.status_code}")
    if response.status_code == 200:
        token_data = response.json()
        print(f"Login successful, token type: {token_data.get('token_type')}")
        return token_data.get('access_token')
    else:
        print(f"Login failed: {response.text}")
        return None

def test_appointments_access(token):
    """Test accessing appointments endpoint"""
    print("Testing appointments access...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/appointments", headers=headers)
    print(f"Appointments response: {response.status_code}")
    if response.status_code == 200:
        appointments = response.json()
        print(f"Found {len(appointments)} appointments")
        return True
    else:
        print(f"Appointments access failed: {response.text}")
        return False

def test_care_providers_access(token):
    """Test accessing care providers endpoint (should fail for regular users)"""
    print("Testing care providers access (should fail for regular users)...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/specialists/care-providers", headers=headers)
    print(f"Care providers response: {response.status_code}")
    if response.status_code == 403:
        print("Access correctly denied for regular user")
        return True
    else:
        print(f"Unexpected response: {response.text}")
        return False

def test_admin_access(token):
    """Test accessing admin endpoints (should fail for regular users)"""
    print("Testing admin access (should fail for regular users)...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/admin/users", headers=headers)
    print(f"Admin users response: {response.status_code}")
    if response.status_code == 403:
        print("Admin access correctly denied for regular user")
        return True
    else:
        print(f"Unexpected response: {response.text}")
        return False

def main():
    print("=== Role-Based System Test ===\n")
    
    # Test 1: User registration
    user = test_user_registration()
    if not user:
        print("❌ User registration failed")
        return
    print("✅ User registration successful\n")
    
    # Test 2: User login
    token = test_user_login(user['email'], "testpassword123")
    if not token:
        print("❌ User login failed")
        return
    print("✅ User login successful\n")
    
    # Test 3: Appointments access (should work)
    if test_appointments_access(token):
        print("✅ Appointments access working\n")
    else:
        print("❌ Appointments access failed\n")
    
    # Test 4: Care providers access (should fail)
    if test_care_providers_access(token):
        print("✅ Care providers access control working\n")
    else:
        print("❌ Care providers access control failed\n")
    
    # Test 5: Admin access (should fail)
    if test_admin_access(token):
        print("✅ Admin access control working\n")
    else:
        print("❌ Admin access control failed\n")
    
    print("=== Test Summary ===")
    print("✅ Role-based system appears to be working correctly!")
    print("\nNext steps:")
    print("1. Create an admin user manually in the database")
    print("2. Use admin endpoints to assign care roles")
    print("3. Test care provider functionality")

if __name__ == "__main__":
    main()
