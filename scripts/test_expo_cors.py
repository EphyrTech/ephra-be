#!/usr/bin/env python3
"""
Quick CORS test specifically for the Expo app.
Tests if the Expo app URL is properly configured in CORS.
"""

import requests
import sys

def test_expo_cors():
    """Test CORS for the specific Expo app."""
    
    # Your specific URLs
    api_url = "https://jk8c0008w8ggo8ck8o0og480.ephyrtech.com"
    expo_origin = "https://ephra-client--3kqpq6gbi7.expo.app"
    
    print("=== Expo App CORS Test ===")
    print(f"API URL: {api_url}")
    print(f"Expo Origin: {expo_origin}")
    
    # Test 1: Health endpoint
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{api_url}/v1/health", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ API is running")
        else:
            print("   ❌ API health check failed")
            return False
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False
    
    # Test 2: CORS Preflight for auth/login
    print("\n2. Testing CORS preflight for /v1/auth/login...")
    headers = {
        'Origin': expo_origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type',
    }
    
    try:
        response = requests.options(f"{api_url}/v1/auth/login", headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ Preflight request successful")
            
            # Check CORS headers
            allow_origin = response.headers.get('Access-Control-Allow-Origin')
            allow_methods = response.headers.get('Access-Control-Allow-Methods')
            allow_headers = response.headers.get('Access-Control-Allow-Headers')
            
            print(f"   Access-Control-Allow-Origin: {allow_origin}")
            print(f"   Access-Control-Allow-Methods: {allow_methods}")
            print(f"   Access-Control-Allow-Headers: {allow_headers}")
            
            if allow_origin in [expo_origin, "*"]:
                print("   ✅ CORS origin is properly configured")
                return True
            else:
                print("   ❌ CORS origin mismatch!")
                print(f"   Expected: {expo_origin}")
                print(f"   Got: {allow_origin}")
                return False
        else:
            print(f"   ❌ Preflight failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Preflight request failed: {e}")
        return False

def main():
    """Main function."""
    success = test_expo_cors()
    
    print("\n" + "="*50)
    if success:
        print("✅ CORS is properly configured for your Expo app!")
        print("\nYour frontend should now be able to make API requests.")
    else:
        print("❌ CORS configuration issue detected!")
        print("\nTo fix this:")
        print("1. Go to your Coolify dashboard")
        print("2. Find the CORS_ORIGINS environment variable")
        print("3. Update it to include: https://ephra-client--3kqpq6gbi7.expo.app")
        print("4. Example: CORS_ORIGINS=https://ephra-client--3kqpq6gbi7.expo.app,https://ephyrtech.com")
        print("5. Redeploy your application")
        
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
