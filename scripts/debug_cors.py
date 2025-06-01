#!/usr/bin/env python3
"""
CORS debugging script to help diagnose CORS issues.
This script tests CORS configuration and helps identify problems.
"""

import os
import sys
import requests
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def test_cors_preflight(base_url, origin):
    """Test CORS preflight request."""
    print(f"\n🔍 Testing CORS preflight for origin: {origin}")

    # Test the auth/login endpoint specifically
    url = f"{base_url}/v1/auth/login"

    headers = {
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type',
    }

    try:
        response = requests.options(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")

        # Check for CORS headers
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
            'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials'),
        }

        print("   CORS Headers:")
        for header, value in cors_headers.items():
            if value:
                print(f"     ✅ {header}: {value}")
            else:
                print(f"     ❌ {header}: Missing")

        return response.status_code == 200

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return False


def test_actual_request(base_url, origin):
    """Test actual POST request."""
    print(f"\n🔍 Testing actual POST request for origin: {origin}")

    url = f"{base_url}/v1/auth/login"

    headers = {
        'Origin': origin,
        'Content-Type': 'application/json',
    }

    data = {
        "email": "test@example.com",
        "password": "testpassword"
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")

        # Check for CORS headers in response
        cors_origin = response.headers.get('Access-Control-Allow-Origin')
        if cors_origin:
            print(f"   ✅ Access-Control-Allow-Origin: {cors_origin}")
        else:
            print(f"   ❌ Access-Control-Allow-Origin: Missing")

        return response.status_code in [200, 401, 422]  # 401/422 are expected for invalid credentials

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return False


def test_health_endpoint(base_url):
    """Test health endpoint."""
    print(f"\n🔍 Testing health endpoint")

    url = f"{base_url}/v1/health"

    try:
        response = requests.get(url, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        return response.status_code == 200

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return False


def main():
    """Main function to run CORS debugging."""
    print("=== CORS Debugging Tool ===")

    # Get configuration
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"CORS Origins: {settings.CORS_ORIGINS}")

    # Get base URL from environment or use default
    base_url = os.getenv("API_BASE_URL", "https://jk8c0008w8ggo8ck8o0og480.ephyrtech.com")
    print(f"Testing API at: {base_url}")

    # Test origins to check
    test_origins = [
        "https://ephra-client--3kqpq6gbi7.expo.app",  # Your Expo app
        "https://ephyrtech.com",
        "https://www.ephyrtech.com",
        "http://localhost:3000",
        "http://localhost:19006",
        "https://jk8c0008w8ggo8ck8o0og480.ephyrtech.com",  # Same origin
    ]

    # Add configured CORS origins to test list
    for origin in settings.CORS_ORIGINS:
        if origin not in test_origins and origin != "*":
            test_origins.append(origin)

    print(f"\nTesting origins: {test_origins}")

    # Test health endpoint first
    health_ok = test_health_endpoint(base_url)

    if not health_ok:
        print("\n❌ Health endpoint failed - API may not be running")
        sys.exit(1)

    # Test CORS for each origin
    results = {}

    for origin in test_origins:
        print(f"\n{'='*60}")
        print(f"Testing origin: {origin}")
        print(f"{'='*60}")

        preflight_ok = test_cors_preflight(base_url, origin)
        actual_ok = test_actual_request(base_url, origin)

        results[origin] = {
            'preflight': preflight_ok,
            'actual': actual_ok
        }

    # Summary
    print(f"\n{'='*60}")
    print("CORS Test Summary")
    print(f"{'='*60}")

    for origin, result in results.items():
        preflight_status = "✅" if result['preflight'] else "❌"
        actual_status = "✅" if result['actual'] else "❌"
        print(f"{origin}")
        print(f"  Preflight: {preflight_status}")
        print(f"  Actual:    {actual_status}")

    # Recommendations
    print(f"\n{'='*60}")
    print("Recommendations")
    print(f"{'='*60}")

    failed_origins = [origin for origin, result in results.items()
                     if not result['preflight'] or not result['actual']]

    if failed_origins:
        print("❌ CORS issues detected!")
        print("\nPossible solutions:")
        print("1. Check that CORS_ORIGINS environment variable includes your frontend domain")
        print("2. Verify the frontend is using the correct API URL")
        print("3. Check that the API server is properly configured")
        print("4. Ensure no proxy/CDN is stripping CORS headers")

        print(f"\nCurrent CORS_ORIGINS: {settings.CORS_ORIGINS}")
        print(f"Failed origins: {failed_origins}")

        if "*" not in settings.CORS_ORIGINS:
            print("\n💡 Consider temporarily adding '*' to CORS_ORIGINS for testing")
    else:
        print("✅ All CORS tests passed!")


if __name__ == "__main__":
    main()
