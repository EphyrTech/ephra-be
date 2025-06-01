#!/bin/bash
set -e

echo "=== Testing Production Setup Locally ==="

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install Docker Compose."
    exit 1
fi

# Check if required environment variables are set
if [[ -z "$DB_PASSWORD" ]]; then
    echo "⚠️  DB_PASSWORD not set. Using default for testing..."
    export DB_PASSWORD="test_password_123"
fi

if [[ -z "$SECRET_KEY" ]]; then
    echo "⚠️  SECRET_KEY not set. Using default for testing..."
    export SECRET_KEY="test_secret_key_for_local_testing_only"
fi

if [[ -z "$CORS_ORIGINS" ]]; then
    echo "⚠️  CORS_ORIGINS not set. Using default for testing..."
    export CORS_ORIGINS="http://localhost:3000,http://localhost:3001"
fi

if [[ -z "$FRONTEND_URL" ]]; then
    echo "⚠️  FRONTEND_URL not set. Using default for testing..."
    export FRONTEND_URL="http://localhost:3000"
fi

echo "Environment variables set:"
echo "  DB_PASSWORD: [HIDDEN]"
echo "  SECRET_KEY: [HIDDEN]"
echo "  CORS_ORIGINS: $CORS_ORIGINS"
echo "  FRONTEND_URL: $FRONTEND_URL"

# Build and start the production setup
echo ""
echo "🔨 Building production containers..."
docker-compose -f docker-compose.prod.yml build

echo ""
echo "🚀 Starting production containers..."
docker-compose -f docker-compose.prod.yml up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if containers are running
echo ""
echo "📊 Container status:"
docker-compose -f docker-compose.prod.yml ps

# Check logs
echo ""
echo "📋 Recent logs from API container:"
docker-compose -f docker-compose.prod.yml logs --tail=20 api

# Test health endpoint
echo ""
echo "🏥 Testing health endpoint..."
sleep 5  # Give a bit more time for the app to start

if curl -f http://localhost:3000/v1/health > /dev/null 2>&1; then
    echo "✅ Health endpoint is responding!"
    echo "   URL: http://localhost:3000/v1/health"
else
    echo "❌ Health endpoint is not responding"
    echo "   Checking logs for errors..."
    docker-compose -f docker-compose.prod.yml logs api
fi

# Test API documentation (should be disabled in production)
echo ""
echo "📚 Testing API documentation (should be disabled in production)..."
if curl -f http://localhost:3000/docs > /dev/null 2>&1; then
    echo "⚠️  API documentation is available (unexpected in production)"
    echo "   URL: http://localhost:3000/docs"
else
    echo "✅ API documentation is properly disabled in production"
fi

# Check migration status
echo ""
echo "🔍 Checking migration status..."
docker-compose -f docker-compose.prod.yml exec api python scripts/check_migrations.py

echo ""
echo "=== Test Summary ==="
echo "✅ Production setup test completed!"
echo ""
echo "Available endpoints:"
echo "  - API: http://localhost:3000"
echo "  - Health: http://localhost:3000/v1/health"
echo "  - Docs: DISABLED (production environment)"
echo ""
echo "To stop the test environment:"
echo "  docker-compose -f docker-compose.prod.yml down"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.prod.yml logs -f"
