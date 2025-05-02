#!/bin/bash
set -e

# Make the script executable
chmod +x ./scripts/find_port.py

# Find an available port
PORT=$(python ./scripts/find_port.py 8000)
echo "Starting FastAPI application on port $PORT"

# Export the port as an environment variable for docker-compose
export API_PORT=$PORT

# Start the application with the available port
echo "Starting FastAPI application on port $PORT"
echo "API will be available at http://localhost:$PORT"
echo "API documentation will be available at http://localhost:$PORT/docs"

uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
