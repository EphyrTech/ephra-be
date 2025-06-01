# Database Seeding

This document explains how to use the database seeding functionality in the Ephra FastAPI backend.

## Overview

The database seeding system creates initial users with different roles for development and testing purposes:

- **Admin user**: System administrator with full access
- **Care providers**: Mental health therapists, physical therapists, and counselors
- **Regular users**: Standard users for testing the application

## Environment Variables

Configure seeding through environment variables:

### Required for Production

```bash
# Enable/disable seeding
SEED_DATABASE=true

# Admin credentials
SEED_ADMIN_EMAIL=admin@yourdomain.com
SEED_ADMIN_PASSWORD=your_secure_admin_password

# Care provider password (used for all care providers)
SEED_CARE_PROVIDER_PASSWORD=your_secure_care_provider_password

# Regular user password (used for all regular users)
SEED_USER_PASSWORD=your_secure_user_password
```

### Default Values (Development)

If environment variables are not set, these defaults are used:

```bash
SEED_ADMIN_EMAIL=admin@ephra.com
SEED_ADMIN_PASSWORD=admin123
SEED_CARE_PROVIDER_PASSWORD=care123
SEED_USER_PASSWORD=user123
```

## Usage

### Development Environment

1. **Manual seeding**:
   ```bash
   # Run seeding script directly
   docker compose exec api python scripts/seed_database.py
   
   # Or use the convenience script
   ./scripts/seed_db.sh
   ```

2. **Automatic seeding** (add to docker-compose.yml):
   ```yaml
   environment:
     - SEED_DATABASE=true
     - SEED_ADMIN_PASSWORD=your_password
     # ... other variables
   ```

### Production Environment

1. **Set environment variables** in your deployment platform (Coolify, etc.):
   ```bash
   SEED_DATABASE=true
   SEED_ADMIN_EMAIL=admin@yourdomain.com
   SEED_ADMIN_PASSWORD=your_secure_password
   SEED_CARE_PROVIDER_PASSWORD=care_provider_password
   SEED_USER_PASSWORD=user_password
   ```

2. **Deploy**: The seeding will run automatically during startup if `SEED_DATABASE=true`

## Created Accounts

### Admin User
- **Email**: Configurable via `SEED_ADMIN_EMAIL`
- **Role**: ADMIN
- **Access**: Full system administration

### Care Providers
- **dr.sarah@ephra.com** - Mental Health Therapist
- **dr.mike@ephra.com** - Physical Therapist  
- **dr.emma@ephra.com** - Counselor
- **Password**: Configurable via `SEED_CARE_PROVIDER_PASSWORD`
- **Role**: CARE_PROVIDER

### Regular Users
- **john.doe@example.com** - Test User 1
- **jane.smith@example.com** - Test User 2
- **demo@ephra.com** - Demo User
- **Password**: Configurable via `SEED_USER_PASSWORD`
- **Role**: USER

## Sample Data

The seeding also creates:
- Care provider profiles with specialties, rates, and experience
- Sample availability slots for the next week
- A sample appointment between a user and care provider
- A sample journal entry

## Security Considerations

### Production Deployment

1. **Always use strong passwords** in production
2. **Use environment variables** - never hardcode credentials
3. **Disable seeding** after initial setup by setting `SEED_DATABASE=false`
4. **Change default passwords** immediately after deployment

### Recommended Password Policy

- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, and symbols
- Unique passwords for each role
- Use a password manager to generate secure passwords

## Integration with start_prod.sh

The seeding is integrated into the production startup script:

1. Database connection is established
2. Migrations are run
3. **Seeding runs** (if enabled)
4. Application starts

This ensures the database is properly initialized on first deployment.

## Troubleshooting

### Seeding Fails
- Check database connectivity
- Verify environment variables are set correctly
- Check logs for specific error messages
- Ensure migrations have run successfully

### Duplicate Users
- The script checks for existing users
- In development, it prompts to continue
- In production, it automatically continues (won't create duplicates)

### Permission Issues
- Ensure the application has database write permissions
- Check that the database user has CREATE and INSERT privileges

## Example Coolify Configuration

```bash
# Environment Variables in Coolify
SEED_DATABASE=true
SEED_ADMIN_EMAIL=admin@yourdomain.com
SEED_ADMIN_PASSWORD=SuperSecureAdminPass123!
SEED_CARE_PROVIDER_PASSWORD=CareProviderPass456!
SEED_USER_PASSWORD=UserPass789!
```

## Testing the Seeded Accounts

After seeding, test the accounts:

```bash
# Test admin login
curl -X POST "https://your-api-domain.com/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@yourdomain.com", "password": "your_admin_password"}'

# Test care provider login
curl -X POST "https://your-api-domain.com/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "dr.sarah@ephra.com", "password": "your_care_provider_password"}'
```

## Disabling Seeding

To disable seeding after initial setup:

```bash
SEED_DATABASE=false
```

Or remove the environment variable entirely.
