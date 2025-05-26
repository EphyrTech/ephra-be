# Coolify Deployment Guide for Ephra FastAPI

This guide explains how to deploy the Ephra FastAPI backend using Coolify.

## Prerequisites

1. A Coolify instance running on your server
2. A domain name pointing to your Coolify server
3. Docker and Docker Compose support in Coolify

## Deployment Steps

### 1. Create a New Service in Coolify

1. Log into your Coolify dashboard
2. Create a new **Docker Compose** service
3. Connect your Git repository containing this project
4. Set the **Build Pack** to "Docker Compose"
5. Set the **Docker Compose File** path to `ephra-fastapi/docker-compose.prod.yml`

### 2. Configure Environment Variables

In Coolify's environment settings, add the following **REQUIRED** variables:

```bash
DOMAIN=your-api-domain.com
DB_PASSWORD=your-secure-database-password
SECRET_KEY=your-very-secure-secret-key-for-jwt-tokens
CORS_ORIGINS=https://your-frontend-domain.com,https://your-app-domain.com
FRONTEND_URL=https://your-frontend-domain.com
```

### 3. Optional Environment Variables

For full functionality, also configure:

```bash
# Google OAuth (for social login)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-email-app-password
EMAIL_FROM=noreply@your-domain.com
```

### 4. Domain Configuration

1. In Coolify, set up your domain for the service
2. Enable **HTTPS/SSL** (Let's Encrypt)
3. The API will be available at `https://your-api-domain.com`

### 5. Database Setup

The PostgreSQL database will be automatically created and configured. The database data will persist in Docker volumes managed by Coolify.

### 6. Health Checks

The service includes health checks that Coolify will use to monitor the application:
- API health check: `GET /v1/health`
- Database health check: `pg_isready`

## Post-Deployment

### Database Migrations

After the first deployment, run database migrations:

1. Access the API container in Coolify's terminal
2. Run: `alembic upgrade head`

### Verify Deployment

1. Check the health endpoint: `https://your-api-domain.com/v1/health`
2. Verify the API documentation: `https://your-api-domain.com/docs`

## File Structure

The deployment uses the following persistent volumes:
- `postgres_data`: Database files
- `uploads_data`: User uploaded files
- `logs_data`: Application logs
- `static_data`: Static files

## Troubleshooting

### Common Issues

1. **Port already allocated error**:
   - This usually means another service is using port 8000
   - The docker-compose.prod.yml has been configured to avoid this
   - If it persists, check if you have other services running on the same Coolify instance
   - Try stopping other services temporarily or use a different port

2. **CORS_ORIGINS parsing error**:
   - Fixed in the latest version - CORS_ORIGINS now accepts comma-separated values
   - Example: `CORS_ORIGINS=https://app.com,https://admin.app.com`
   - For single domain: `CORS_ORIGINS=https://app.com`
   - For all origins: `CORS_ORIGINS=*`

3. **Service won't start**: Check environment variables are set correctly

4. **Database connection errors**: Verify DB_PASSWORD is set

5. **CORS errors**: Ensure CORS_ORIGINS includes your frontend domain

6. **SSL certificate issues**: Verify domain DNS is pointing to Coolify server

7. **Container networking issues**:
   - Coolify manages networking automatically
   - No need to expose ports manually
   - Let Coolify handle reverse proxy routing

### Logs

Access logs through Coolify's interface or check the `logs_data` volume.

## Security Notes

1. Use strong, unique passwords for DB_PASSWORD and SECRET_KEY
2. Limit CORS_ORIGINS to only your frontend domains
3. Use app-specific passwords for Gmail SMTP
4. Regularly update the Docker images

## Scaling

Coolify can scale the API service horizontally. The database should remain as a single instance for data consistency.
