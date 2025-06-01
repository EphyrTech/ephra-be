#!/bin/bash
set -e

echo "=== Production Startup Script ==="
echo "Environment: ${ENVIRONMENT:-unknown}"
echo "Database URL: ${DATABASE_URL:-not set}"

# Function to wait for database to be ready
wait_for_db() {
    echo "Waiting for database to be ready..."

    # Extract database connection details from DATABASE_URL
    # Format: postgresql://user:password@host:port/dbname
    if [[ -z "$DATABASE_URL" ]]; then
        echo "ERROR: DATABASE_URL environment variable is not set"
        exit 1
    fi

    # Use Python to parse the DATABASE_URL and test connection
    python3 << 'EOF'
import os
import sys
import time
import psycopg2
from urllib.parse import urlparse

def wait_for_database(max_attempts=30, delay=2):
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found")
        sys.exit(1)

    # Parse the database URL
    parsed = urlparse(database_url)

    for attempt in range(max_attempts):
        try:
            print(f"Attempt {attempt + 1}/{max_attempts}: Connecting to database...")
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:],  # Remove leading slash
                connect_timeout=5
            )
            conn.close()
            print("✅ Database connection successful!")
            return True
        except psycopg2.OperationalError as e:
            print(f"❌ Database connection failed: {e}")
            if attempt < max_attempts - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("❌ Max attempts reached. Database is not ready.")
                sys.exit(1)

    return False

if __name__ == "__main__":
    wait_for_database()
EOF

    echo "Database is ready!"
}

# Function to run database migrations
run_migrations() {
    echo "Running database migrations..."

    # Check if alembic is available
    if ! command -v alembic &> /dev/null; then
        echo "ERROR: alembic command not found"
        exit 1
    fi

    # Run migrations
    echo "Executing: alembic upgrade head"
    alembic upgrade head

    if [ $? -eq 0 ]; then
        echo "✅ Database migrations completed successfully!"
    else
        echo "❌ Database migrations failed!"
        exit 1
    fi
}

# Function to seed database with initial data
seed_database() {
    echo "Seeding database with initial data..."

    # Check if seeding is enabled
    if [[ "${SEED_DATABASE:-false}" != "true" ]]; then
        echo "⏭️  Database seeding disabled (set SEED_DATABASE=true to enable)"
        return 0
    fi

    # Check if Python script exists
    if [[ ! -f "scripts/seed_database.py" ]]; then
        echo "⚠️  Seeding script not found at scripts/seed_database.py"
        return 0
    fi

    echo "🌱 Running database seeding script..."
    python scripts/seed_database.py

    if [ $? -eq 0 ]; then
        echo "✅ Database seeding completed successfully!"
    else
        echo "⚠️  Database seeding failed, but continuing with startup..."
        # Don't exit on seeding failure in production
    fi
}

# Function to start the application
start_application() {
    echo "Starting FastAPI application with Gunicorn..."
    echo "Workers: 4"
    echo "Worker class: uvicorn.workers.UvicornWorker"
    echo "Bind: 0.0.0.0:8000"

    exec gunicorn main:app \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --access-logfile - \
        --error-logfile - \
        --log-level info \
        --timeout 120 \
        --keep-alive 2 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --preload
}

# Main execution flow
main() {
    echo "Starting production deployment sequence..."

    # Step 1: Wait for database
    wait_for_db

    # Step 2: Run migrations
    run_migrations

    # Step 3: Seed database (optional)
    seed_database

    # Step 4: Start the application
    start_application
}

# Execute main function
main "$@"
