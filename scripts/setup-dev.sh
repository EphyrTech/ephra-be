#!/bin/bash
set -e

# Create directories if they don't exist
mkdir -p uploads

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example"
    cp .env.example .env
fi

# Start the containers
docker-compose up -d

# Wait for the database to be ready
echo "Waiting for database to be ready..."
sleep 5

# Run database migrations
echo "Running database migrations..."
docker-compose exec api alembic revision --autogenerate -m "initial"
docker-compose exec api alembic upgrade head

# Install additional development dependencies with uv if needed
echo "Installing additional development dependencies with uv..."
docker-compose exec api uv pip install --system pytest pytest-cov pytest-asyncio httpx

echo "Development environment is ready!"
echo "API is running at: http://localhost:8000"
echo "API documentation is available at: http://localhost:8000/docs"
echo "PgAdmin is available at: http://localhost:5050"
echo "  - Email: admin@example.com"
echo "  - Password: admin"
echo ""
echo "Using uv for Python package management:"
echo "  - Install packages: docker-compose exec api uv pip install <package>"
echo "  - Update requirements.txt: docker-compose exec api uv pip freeze > requirements.txt"
