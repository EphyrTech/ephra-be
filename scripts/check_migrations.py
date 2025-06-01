#!/usr/bin/env python3
"""
Script to check the current migration status and verify database schema.
This can be used to debug migration issues in production.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from app.core.config import settings


def check_database_connection():
    """Test database connection."""
    print("🔍 Testing database connection...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Database connection successful!")
            print(f"   PostgreSQL version: {version}")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def check_alembic_version_table():
    """Check if alembic_version table exists and get current revision."""
    print("\n🔍 Checking alembic version table...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                );
            """))
            table_exists = result.fetchone()[0]
            
            if table_exists:
                print("✅ alembic_version table exists")
                
                # Get current revision
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                current_revision = result.fetchone()
                if current_revision:
                    print(f"   Current revision: {current_revision[0]}")
                    return current_revision[0]
                else:
                    print("   No revision found in alembic_version table")
                    return None
            else:
                print("❌ alembic_version table does not exist")
                return None
                
    except Exception as e:
        print(f"❌ Error checking alembic version table: {e}")
        return None


def check_available_migrations():
    """Check available migration files."""
    print("\n🔍 Checking available migrations...")
    try:
        # Get alembic config
        alembic_cfg = Config("alembic.ini")
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        
        # Get all revisions
        revisions = list(script_dir.walk_revisions())
        print(f"✅ Found {len(revisions)} migration files:")
        
        for revision in reversed(revisions):  # Show in chronological order
            print(f"   - {revision.revision}: {revision.doc}")
            
        return revisions
        
    except Exception as e:
        print(f"❌ Error checking migrations: {e}")
        return []


def check_migration_status():
    """Check if database is up to date with migrations."""
    print("\n🔍 Checking migration status...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        
        # Get alembic config
        alembic_cfg = Config("alembic.ini")
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            head_rev = script_dir.get_current_head()
            
            print(f"   Current revision: {current_rev}")
            print(f"   Head revision: {head_rev}")
            
            if current_rev == head_rev:
                print("✅ Database is up to date with migrations")
                return True
            else:
                print("❌ Database is NOT up to date with migrations")
                
                # Show pending migrations
                pending = []
                for revision in script_dir.iterate_revisions(head_rev, current_rev):
                    if revision.revision != current_rev:
                        pending.append(revision)
                
                if pending:
                    print(f"   Pending migrations ({len(pending)}):")
                    for rev in pending:
                        print(f"     - {rev.revision}: {rev.doc}")
                
                return False
                
    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        return False


def main():
    """Main function to run all checks."""
    print("=== Database Migration Status Check ===")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'unknown')}")
    print(f"Database URL: {settings.DATABASE_URL}")
    
    # Run all checks
    db_ok = check_database_connection()
    if not db_ok:
        sys.exit(1)
    
    current_rev = check_alembic_version_table()
    available_migrations = check_available_migrations()
    migration_status_ok = check_migration_status()
    
    print("\n=== Summary ===")
    if migration_status_ok:
        print("✅ All checks passed! Database is properly migrated.")
        sys.exit(0)
    else:
        print("❌ Migration issues detected. Please run migrations.")
        sys.exit(1)


if __name__ == "__main__":
    main()
