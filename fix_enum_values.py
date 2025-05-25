#!/usr/bin/env python3
"""
Script to fix enum values in the database from lowercase to uppercase.
This addresses the validation error where the database has 'user', 'care', 'admin'
but the Pydantic schema expects 'USER', 'CARE', 'ADMIN'.
"""

import asyncio
from sqlalchemy import create_engine, text
from app.core.config import settings

def fix_enum_values():
    """Fix enum values in the database."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as connection:
        try:
            print("Checking current enum values...")
            
            # Check current role values
            result = connection.execute(text("SELECT DISTINCT role FROM users WHERE role IS NOT NULL"))
            current_roles = [row[0] for row in result.fetchall()]
            print(f"Current role values: {current_roles}")
            
            # Check current specialty values
            result = connection.execute(text("SELECT DISTINCT specialty FROM users WHERE specialty IS NOT NULL"))
            current_specialties = [row[0] for row in result.fetchall()]
            print(f"Current specialty values: {current_specialties}")
            
            # Update role values if they are lowercase
            if any(role in ['user', 'care', 'admin'] for role in current_roles):
                print("Updating role values to uppercase...")
                
                # First, temporarily allow the column to be text
                connection.execute(text("ALTER TABLE users ALTER COLUMN role TYPE text"))
                
                # Update the values
                connection.execute(text("UPDATE users SET role = UPPER(role) WHERE role IS NOT NULL"))
                
                # Convert back to enum
                connection.execute(text("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole"))
                
                print("Role values updated successfully!")
            
            # Update specialty values if they are lowercase
            if any(specialty in ['mental', 'physical'] for specialty in current_specialties):
                print("Updating specialty values to uppercase...")
                
                # First, temporarily allow the column to be text
                connection.execute(text("ALTER TABLE users ALTER COLUMN specialty TYPE text"))
                
                # Update the values
                connection.execute(text("UPDATE users SET specialty = UPPER(specialty) WHERE specialty IS NOT NULL"))
                
                # Convert back to enum
                connection.execute(text("ALTER TABLE users ALTER COLUMN specialty TYPE specialisttype USING specialty::specialisttype"))
                
                print("Specialty values updated successfully!")
            
            # Commit the changes
            connection.commit()
            
            print("All enum values have been fixed!")
            
        except Exception as e:
            print(f"Error fixing enum values: {e}")
            connection.rollback()
            raise

if __name__ == "__main__":
    fix_enum_values()
