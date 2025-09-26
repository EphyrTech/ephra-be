#!/usr/bin/env python3
"""
Script to create admin users in the database.
This script helps create admin users that can be used with the admin panel.
"""

import sys
import os
import getpass
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, UserRole
from app.core.security import get_password_hash
from app.core.admin_auth import verify_admin_users_exist


def create_admin_user(db: Session, email: str, password: str, name: str = None) -> dict:
    """Create an admin user in the database"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            return {
                "success": False,
                "error": f"User with email {email} already exists",
                "user_id": existing_user.id,
                "current_role": existing_user.role.value
            }
        
        # Create new admin user
        admin_user = User(
            email=email,
            name=name or "Admin User",
            first_name=name.split()[0] if name and " " in name else "Admin",
            last_name=name.split()[-1] if name and " " in name else "User",
            display_name=name or "Admin User",
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        return {
            "success": True,
            "message": "Admin user created successfully",
            "user_id": admin_user.id,
            "email": admin_user.email,
            "name": admin_user.name
        }
        
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": f"Error creating admin user: {str(e)}"
        }


def promote_user_to_admin(db: Session, email: str) -> dict:
    """Promote an existing user to admin role"""
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return {
                "success": False,
                "error": f"User with email {email} not found"
            }
        
        if user.role == UserRole.ADMIN:
            return {
                "success": False,
                "error": f"User {email} is already an admin"
            }
        
        old_role = user.role.value
        user.role = UserRole.ADMIN
        db.commit()
        
        return {
            "success": True,
            "message": f"User promoted from {old_role} to admin",
            "user_id": user.id,
            "email": user.email,
            "old_role": old_role,
            "new_role": "admin"
        }
        
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": f"Error promoting user: {str(e)}"
        }


def main():
    """Main function to create admin users"""
    print("👤 Admin User Management")
    print("=" * 30)
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Show current admin status
        print("\nCurrent admin status:")
        admin_verification = verify_admin_users_exist(db)
        if admin_verification["success"]:
            print(f"  Database admin users: {admin_verification['admin_count']}")
            print(f"  Superadmin configured: {admin_verification.get('superadmin_configured', False)}")
        
        print("\nOptions:")
        print("1. Create new admin user")
        print("2. Promote existing user to admin")
        print("3. List current admin users")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == "1":
            # Create new admin user
            print("\n📝 Creating new admin user")
            email = input("Email: ").strip()
            if not email or "@" not in email:
                print("❌ Invalid email address")
                return 1
            
            name = input("Full name (optional): ").strip()
            password = getpass.getpass("Password: ")
            confirm_password = getpass.getpass("Confirm password: ")
            
            if password != confirm_password:
                print("❌ Passwords do not match")
                return 1
            
            if len(password) < 8:
                print("❌ Password must be at least 8 characters long")
                return 1
            
            result = create_admin_user(db, email, password, name)
            if result["success"]:
                print(f"✅ {result['message']}")
                print(f"   User ID: {result['user_id']}")
                print(f"   Email: {result['email']}")
                print(f"   Name: {result['name']}")
            else:
                print(f"❌ {result['error']}")
                if "already exists" in result["error"]:
                    print(f"   Current role: {result.get('current_role', 'unknown')}")
        
        elif choice == "2":
            # Promote existing user
            print("\n⬆️  Promoting existing user to admin")
            email = input("Email of user to promote: ").strip()
            if not email:
                print("❌ Email is required")
                return 1
            
            result = promote_user_to_admin(db, email)
            if result["success"]:
                print(f"✅ {result['message']}")
                print(f"   User ID: {result['user_id']}")
                print(f"   Email: {result['email']}")
            else:
                print(f"❌ {result['error']}")
        
        elif choice == "3":
            # List current admin users
            print("\n📋 Current admin users:")
            if admin_verification["success"] and admin_verification["admins"]:
                for admin in admin_verification["admins"]:
                    print(f"  - {admin['email']} ({admin['name']})")
                    print(f"    ID: {admin['id']}")
                    print(f"    Has Password: {admin['has_password']}")
                    print(f"    Created: {admin['created_at']}")
                    print()
            else:
                print("  No admin users found")
        
        elif choice == "4":
            print("👋 Goodbye!")
            return 0
        
        else:
            print("❌ Invalid option")
            return 1
    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        db.close()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
