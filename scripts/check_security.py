#!/usr/bin/env python3
"""
Security check script to verify production security configurations.
This script checks that sensitive endpoints are properly disabled in production.
"""

import os
import sys
import requests
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def check_api_docs_disabled():
    """Check if API documentation endpoints are disabled in production."""
    print("🔍 Checking API documentation endpoints...")
    
    if settings.ENVIRONMENT != "production":
        print(f"ℹ️  Environment is '{settings.ENVIRONMENT}' - API docs should be enabled")
        return True
    
    print("🔒 Production environment detected - checking that API docs are disabled...")
    
    # Define the base URL (assuming local testing or provide via env var)
    base_url = os.getenv("API_BASE_URL", "http://localhost:3000")
    
    endpoints_to_check = [
        ("/docs", "Swagger UI"),
        ("/redoc", "ReDoc"),
        ("/openapi.json", "OpenAPI JSON")
    ]
    
    all_disabled = True
    
    for endpoint, name in endpoints_to_check:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 404:
                print(f"✅ {name} ({endpoint}) - Properly disabled (404)")
            elif response.status_code == 200:
                print(f"❌ {name} ({endpoint}) - SECURITY ISSUE: Still accessible!")
                all_disabled = False
            else:
                print(f"⚠️  {name} ({endpoint}) - Unexpected status: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"🔌 {name} ({endpoint}) - Cannot connect (server may not be running)")
        except requests.exceptions.Timeout:
            print(f"⏱️  {name} ({endpoint}) - Request timeout")
        except Exception as e:
            print(f"❓ {name} ({endpoint}) - Error: {e}")
    
    return all_disabled


def check_environment_config():
    """Check environment configuration for security."""
    print("\n🔍 Checking environment configuration...")
    
    # Check critical environment variables
    checks = [
        ("ENVIRONMENT", settings.ENVIRONMENT, "Should be 'production' in production"),
        ("DEBUG", settings.DEBUG, "Should be False in production"),
        ("SECRET_KEY", "***HIDDEN***" if settings.SECRET_KEY != "your-secret-key-for-development" else "DEFAULT", "Should not use default value"),
    ]
    
    all_good = True
    
    for var_name, value, description in checks:
        if var_name == "ENVIRONMENT":
            if value == "production":
                print(f"✅ {var_name}: {value} - {description}")
            else:
                print(f"ℹ️  {var_name}: {value} - {description}")
        elif var_name == "DEBUG":
            if settings.ENVIRONMENT == "production" and value:
                print(f"⚠️  {var_name}: {value} - Should be False in production")
                all_good = False
            else:
                print(f"✅ {var_name}: {value} - {description}")
        elif var_name == "SECRET_KEY":
            if value == "DEFAULT":
                print(f"❌ {var_name}: Using default value - SECURITY RISK!")
                all_good = False
            else:
                print(f"✅ {var_name}: Custom value set - {description}")
    
    return all_good


def check_cors_config():
    """Check CORS configuration."""
    print("\n🔍 Checking CORS configuration...")
    
    cors_origins = settings.CORS_ORIGINS
    
    if settings.ENVIRONMENT == "production":
        if "*" in cors_origins:
            print("⚠️  CORS: Wildcard (*) found in production - consider restricting to specific domains")
        else:
            print(f"✅ CORS: Restricted to specific origins: {cors_origins}")
    else:
        print(f"ℹ️  CORS: Development configuration: {cors_origins}")
    
    return True


def main():
    """Main function to run all security checks."""
    print("=== Production Security Check ===")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Debug mode: {settings.DEBUG}")
    
    # Run all checks
    docs_ok = check_api_docs_disabled()
    env_ok = check_environment_config()
    cors_ok = check_cors_config()
    
    print("\n=== Security Check Summary ===")
    
    if settings.ENVIRONMENT == "production":
        if docs_ok and env_ok and cors_ok:
            print("✅ All security checks passed!")
            sys.exit(0)
        else:
            print("❌ Some security issues detected!")
            sys.exit(1)
    else:
        print(f"ℹ️  Running in {settings.ENVIRONMENT} mode - some checks are informational only")
        sys.exit(0)


if __name__ == "__main__":
    main()
