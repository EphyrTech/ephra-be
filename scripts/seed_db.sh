#!/bin/bash

# Database seeding script for Docker environment
# This script runs the Python seeding script inside the Docker container

set -e

echo "🌱 Seeding Ephra database..."
echo ""

# Check if we're running in Docker
if [ -f /.dockerenv ]; then
    echo "📦 Running inside Docker container"
    python scripts/seed_database.py
else
    echo "🐳 Running from host - executing in Docker container"

    # Check if containers are running
    if ! docker compose ps | grep -q "api.*Up"; then
        echo "❌ API container is not running. Please start it first:"
        echo "   docker compose up -d api"
        exit 1
    fi

    # Run the seeding script in the container
    docker compose exec api python scripts/seed_database.py
fi

echo ""
echo "✅ Database seeding completed!"
echo ""
echo "🔗 You can now test the API with these accounts:"
echo "   • Admin: admin@ephra.com / admin123"
echo "   • Therapist: dr.sarah@ephra.com / therapist123"
echo "   • Physical Therapist: dr.mike@ephra.com / physio123"
echo "   • Counselor: dr.emma@ephra.com / counselor123"
echo "   • User: john.doe@example.com / user123"
echo "   • Demo: demo@ephra.com / demo123"
echo ""
echo "🌐 API Documentation: http://localhost:8000/docs"
echo "🏥 Health Check: http://localhost:8000/v1/health"
