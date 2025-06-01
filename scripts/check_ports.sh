#!/bin/bash

# Port Conflict Checker for Coolify Deployment
# This script helps identify potential port conflicts before deployment

echo "🔍 Checking for port conflicts..."
echo "=================================="

# Check if port 8000 is in use
echo "Checking port 8000 (API):"
if lsof -i :8000 >/dev/null 2>&1; then
    echo "❌ Port 8000 is currently in use:"
    lsof -i :8000
    echo ""
    echo "💡 Solutions:"
    echo "   1. Stop the service using port 8000"
    echo "   2. The docker-compose.prod.yml has been configured to avoid this"
    echo "   3. Coolify should handle port management automatically"
else
    echo "✅ Port 8000 is available"
fi

echo ""

# Check if port 5432 is in use (PostgreSQL)
echo "Checking port 5432 (PostgreSQL):"
if lsof -i :5432 >/dev/null 2>&1; then
    echo "❌ Port 5432 is currently in use:"
    lsof -i :5432
    echo ""
    echo "💡 This might conflict with the database container"
else
    echo "✅ Port 5432 is available"
fi

echo ""

# Check Docker status
echo "Checking Docker status:"
if docker info >/dev/null 2>&1; then
    echo "✅ Docker is running"
else
    echo "❌ Docker is not running or not accessible"
fi

echo ""

# Check for existing containers with similar names
echo "Checking for existing containers:"
existing_containers=$(docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "(api|db|postgres)" || true)
if [ -n "$existing_containers" ]; then
    echo "⚠️  Found existing containers that might conflict:"
    echo "$existing_containers"
    echo ""
    echo "💡 Consider stopping these containers before deployment"
else
    echo "✅ No conflicting containers found"
fi

echo ""
echo "🚀 Deployment Tips:"
echo "   - Coolify manages networking automatically"
echo "   - No need to expose ports manually in docker-compose"
echo "   - Let Coolify handle reverse proxy and SSL"
echo "   - Check Coolify logs if deployment fails"
