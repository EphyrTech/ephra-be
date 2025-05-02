# Mental Health API

A FastAPI backend for a mental health application with features including user management, journals, media uploads, and appointments.

## Features

- User authentication (email/password and Google OAuth)
- User profile management
- Journal entries
- Appointment scheduling with specialists
- Media file uploads
- RESTful API with OpenAPI documentation
- Comprehensive test suite with pytest
- API versioning
- Rate limiting
- Response caching
- WebSockets for real-time communication
- Health check endpoints
- Metrics and monitoring
- Structured logging
- Service-based architecture
- Background tasks for email sending
- Production deployment with Caddy
- CI/CD with GitHub Actions

## Tech Stack

- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker & Docker Compose
- Alembic (for database migrations)
- uv (fast Python package installer and resolver)
- pytest (for testing)
- Caddy (for HTTPS and reverse proxy)
- GitHub Actions (for CI/CD)

## Development with VS Code Devcontainer

This project includes a devcontainer configuration for VS Code, which provides a consistent development environment with all necessary tools pre-installed. The devcontainer uses Docker Compose to set up the complete development environment including the API, database, and pgAdmin.

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop)
- [VS Code](https://code.visualstudio.com/)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Getting Started with Devcontainer

1. Clone the repository
2. Open the project in VS Code
3. When prompted, click "Reopen in Container" or run the "Dev Containers: Reopen in Container" command from the command palette
4. VS Code will build the Docker container using docker-compose and open the project inside it
5. The API will automatically start in the background thanks to the `postStartCommand` in the devcontainer configuration
6. If you need to run database migrations, run the setup script:

```bash
./scripts/setup-dev.sh
```

- The API will be available at a dynamically assigned port (default: 8000)
- The actual port will be displayed in the terminal when the app starts
- API documentation is available at the same port with the `/docs` path
- PgAdmin is available at [`http://localhost:5050`](http://localhost:5050) (Email: admin@example.com, Password: admin)

### Debugging in the Devcontainer

The devcontainer is configured with debugging capabilities. To debug the application:

1. Open the "Run and Debug" panel in VS Code (Ctrl+Shift+D or Cmd+Shift+D on Mac)
2. Select one of the available debug configurations:
   - **FastAPI**: Debug the main FastAPI application
   - **Python: Current File**: Debug the currently open Python file
   - **Python: Debug Tests**: Debug tests
3. Set breakpoints in your code by clicking in the gutter next to the line numbers
4. Press F5 or click the green play button to start debugging

The application will automatically reload when you make changes to the code, thanks to the `--reload` flag in the uvicorn command.

### Dynamic Port Assignment

The devcontainer is configured to automatically find an available port if the default port (8000) is busy:

1. When the devcontainer starts, it runs a script that checks if port 8000 is available
2. If port 8000 is busy, it will increment and try the next port (8001, 8002, etc.) until it finds an available one
3. The selected port is saved to a `.port` file and used consistently across restarts
4. The terminal will display the URL with the correct port when the app starts

This ensures you can run multiple instances of the application or work with other services that might use the same port without conflicts.

## Manual Setup (without Devcontainer)

1. Clone the repository
2. Create a `.env` file based on `.env.example`
3. Start the application:

```bash
docker-compose up -d
```

Then run database migrations:

```bash
docker-compose exec api alembic revision --autogenerate -m "initial"
docker-compose exec api alembic upgrade head
```

## Using uv for Package Management

This project uses [uv](https://github.com/astral-sh/uv), a fast Python package installer and resolver, instead of pip. Here's how to use it:

### Installing Packages

```bash
# Inside the container
uv pip install package-name

# From host
docker-compose exec api uv pip install package-name
```

### Updating requirements.txt

```bash
# Inside the container
uv pip freeze > requirements.txt

# From host
docker-compose exec api bash -c "uv pip freeze > requirements.txt"
```

### Installing All Dependencies

```bash
# Inside the container
uv pip install -r requirements.txt

# From host
docker-compose exec api uv pip install -r requirements.txt
```

## Database Migrations

To create a new migration:

```bash
docker-compose exec api alembic revision --autogenerate -m "description"
```

To apply migrations:

```bash
docker-compose exec api alembic upgrade head
```

## Testing

This project includes a comprehensive test suite using pytest. The tests cover all API endpoints and core functionality.

### Running Tests

To run the tests:

```bash
# Inside the container
./scripts/run_tests.sh

# From host
docker-compose exec api ./scripts/run_tests.sh
```

This will run all tests and generate a coverage report.

### Test Structure

- `tests/conftest.py` - Test fixtures and setup
- `tests/test_auth.py` - Authentication endpoint tests
- `tests/test_users.py` - User endpoint tests
- `tests/test_journals.py` - Journal endpoint tests
- `tests/test_appointments.py` - Appointment endpoint tests
- `tests/test_specialists.py` - Specialist endpoint tests
- `tests/test_media.py` - Media upload endpoint tests
- `tests/test_deps.py` - Dependency function tests
- `tests/test_security.py` - Security function tests
- `tests/test_main.py` - Main application tests
- `tests/test_pagination_and_filtering.py` - Tests for pagination and filtering
- `tests/test_error_handling.py` - Tests for error handling and edge cases
- `tests/test_external_services.py` - Tests for external service integrations

### Advanced Test Fixtures

The test suite includes a variety of fixtures to help with testing different scenarios:

- **User Fixtures**: Regular user, admin user, inactive user
- **Data Fixtures**: Single and multiple journals, appointments, specialists
- **Pagination and Filtering**: Parameterized fixtures for testing pagination and search
- **Mock Services**: Mock implementations of external services like Google Auth and email
- **Error Handling**: Fixtures to simulate database errors and other edge cases
- **File Handling**: Mock file fixtures for testing uploads

These fixtures make it easy to test a wide range of scenarios and edge cases.

## Production Deployment

This project includes a production-ready setup with Caddy for HTTPS and reverse proxy.

### Production Prerequisites

- Docker and Docker Compose
- A domain name (optional, but recommended for production)

### Deployment Steps

1. Clone the repository
2. Run the production setup script:

```bash
./scripts/setup-prod.sh
```

This script will:

- Create necessary directories
- Generate a secure secret key
- Prompt for domain name and database password
- Start the containers in production mode
- Run database migrations

### Production Architecture

The production setup includes:

- **API Server**: FastAPI application running with Gunicorn and Uvicorn workers
- **Database**: PostgreSQL for data storage
- **Caddy**: Modern web server providing HTTPS with automatic certificate management and reverse proxy

### CI/CD Pipeline

The project includes a GitHub Actions workflow for continuous integration and deployment:

1. **Test**: Runs the test suite against a PostgreSQL database
2. **Lint**: Checks code quality with black, isort, mypy, and pylint
3. **Build**: Builds a Docker image and pushes it to Docker Hub
4. **Deploy**: Deploys the application to the production server

## Advanced Features

### API Versioning

All endpoints are versioned under `/v1` to allow for future API changes without breaking existing clients.

### Rate Limiting

The API includes rate limiting to prevent abuse. By default, it allows 60 requests per minute per client IP.

### Response Caching

Public endpoints are cached to improve performance. The cache can be configured in the settings.

### WebSockets

Real-time communication is available through WebSockets at `/v1/ws`. Authentication is required via a token query parameter.

Example:

```javascript
const ws = new WebSocket('ws://localhost:8000/v1/ws?token=your_jwt_token');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
ws.send(JSON.stringify({ type: 'echo', message: 'Hello, WebSocket!' }));
```

### Health Checks

Health check endpoints are available at:

- `/v1/health` - Basic health check
- `/v1/health/db` - Database health check

### Metrics and Monitoring

System metrics are available at `/v1/metrics` for monitoring.

### Service-based Architecture

The application uses a service-based architecture for better separation of concerns:

- `JournalService` - Handles journal operations
- `EmailService` - Handles email sending

## API Endpoints

- Authentication
  - POST /v1/auth/register - Register a new user
  - POST /v1/auth/login - Login with email and password
  - POST /v1/auth/google - Authenticate with Google
  - POST /v1/auth/reset-password - Request password reset

- Users
  - GET /v1/users/me - Get current user profile
  - PUT /v1/users/me - Update current user profile
  - DELETE /v1/users/me - Delete user account

- Journals
  - GET /v1/journals - List journal entries
  - POST /v1/journals - Create journal entry
  - GET /v1/journals/{id} - Get a journal entry
  - PUT /v1/journals/{id} - Update a journal entry
  - DELETE /v1/journals/{id} - Delete journal entry

- Media
  - POST /v1/media/upload - Upload media file

- Appointments
  - GET /v1/appointments - List appointments
  - POST /v1/appointments - Create appointment
  - GET /v1/appointments/{id} - Get appointment details
  - PUT /v1/appointments/{id} - Update appointment
  - DELETE /v1/appointments/{id} - Cancel appointment

- Specialists
  - GET /v1/specialists - List specialists
  - GET /v1/specialists/{id} - Get specialist details
  - GET /v1/specialists/{id}/availability - Get specialist availability

- Health
  - GET /v1/health - Basic health check
  - GET /v1/health/db - Database health check

- Metrics
  - GET /v1/metrics - System metrics
  - GET /v1/metrics/prometheus - Prometheus-formatted metrics

- WebSockets
  - WS /v1/ws - WebSocket endpoint
