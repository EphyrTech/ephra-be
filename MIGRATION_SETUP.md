# Database Migration Setup for Production

This document explains the database migration setup for the Ephra FastAPI backend in production environments, particularly when deployed with Coolify.

## Problem Solved

Previously, the production deployment had no automatic database migration step, which meant:
- New database schema changes wouldn't be applied automatically
- Manual intervention was required after each deployment
- Risk of application startup with outdated database schema

## Solution Overview

The solution implements an automatic migration system that:
1. **Waits for database readiness** before attempting migrations
2. **Runs Alembic migrations** automatically on container startup
3. **Starts the application** only after successful migrations
4. **Provides comprehensive logging** for debugging

## Files Modified/Added

### 1. `scripts/start_prod.sh` (NEW)
- **Purpose**: Production startup script that handles the complete deployment sequence
- **Features**:
  - Database readiness check with retry logic
  - Automatic Alembic migration execution
  - Proper error handling and logging
  - Gunicorn startup with production-optimized settings

### 2. `Dockerfile.prod` (MODIFIED)
- **Changes**:
  - Added `postgresql-client` for database connectivity tools
  - Made startup script executable
  - Changed from `CMD` to `ENTRYPOINT` to use the startup script

### 3. `docker-compose.prod.yml` (MODIFIED)
- **Changes**:
  - Fixed hardcoded database password to use `${DB_PASSWORD}` environment variable
  - Maintained proper service dependencies and health checks

### 4. `scripts/check_migrations.py` (NEW)
- **Purpose**: Diagnostic tool for checking migration status
- **Features**:
  - Database connection testing
  - Current migration revision checking
  - Available migrations listing
  - Migration status verification

## How It Works

### Startup Sequence

1. **Container starts** → `scripts/start_prod.sh` is executed
2. **Database wait** → Script waits for PostgreSQL to be ready (max 30 attempts)
3. **Migration check** → Alembic checks current database state
4. **Migration execution** → `alembic upgrade head` applies pending migrations
5. **Application start** → Gunicorn starts with production settings

### Database Readiness Check

The script uses Python with `psycopg2` to test actual database connectivity:
- Parses `DATABASE_URL` environment variable
- Attempts connection with 5-second timeout
- Retries up to 30 times with 2-second delays
- Exits with error if database never becomes ready

### Migration Execution

- Uses Alembic's `upgrade head` command
- Applies all pending migrations in sequence
- Logs success/failure with clear messages
- Stops deployment if migrations fail

## Environment Variables Required

Ensure these environment variables are set in your Coolify deployment:

```bash
# Database connection
DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/mental_health_db
POSTGRES_PASSWORD=your_secure_password_here

# Application settings
SECRET_KEY=your_secret_key
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend-domain.com
FRONTEND_URL=https://your-frontend-domain.com

# Optional settings
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=60
CACHE_TTL_SECONDS=300
```

## Troubleshooting

### Check Migration Status

Run the diagnostic script to check current migration status:

```bash
# Inside the container
python scripts/check_migrations.py
```

### Common Issues

1. **Database not ready**
   - Check if PostgreSQL container is healthy
   - Verify `DATABASE_URL` is correct
   - Check network connectivity between containers

2. **Migration failures**
   - Check Alembic migration files for syntax errors
   - Verify database permissions
   - Check for conflicting schema changes

3. **Application won't start**
   - Check container logs: `docker logs <container_name>`
   - Verify all environment variables are set
   - Check if startup script has execute permissions

### Manual Migration

If you need to run migrations manually:

```bash
# Enter the container
docker exec -it <container_name> bash

# Run migrations
alembic upgrade head

# Check status
python scripts/check_migrations.py
```

## Production Deployment with Coolify

1. **Set environment variables** in Coolify dashboard
2. **Deploy the application** - migrations will run automatically
3. **Monitor logs** to verify successful migration execution
4. **Use health check endpoint** `/v1/health` to verify application status

## Benefits

- ✅ **Zero-downtime deployments** with automatic schema updates
- ✅ **Reliable startup sequence** with proper dependency handling
- ✅ **Comprehensive logging** for debugging and monitoring
- ✅ **Production-ready** with optimized Gunicorn settings
- ✅ **Error handling** prevents broken deployments
- ✅ **Diagnostic tools** for troubleshooting
- ✅ **Security hardened** with disabled API documentation in production

## Security Features

### API Documentation Disabled in Production

For security reasons, the API documentation endpoints are automatically disabled when `ENVIRONMENT=production`:

- **Swagger UI** (`/docs`) - Disabled
- **ReDoc** (`/redoc`) - Disabled
- **OpenAPI JSON** (`/openapi.json`) - Disabled

This prevents potential information disclosure and reduces the attack surface in production.

### Other Security Measures

- Database password is properly externalized via environment variables
- No sensitive information is hardcoded in configuration files
- Production startup script includes security best practices
- CORS origins are properly configured for production domains
