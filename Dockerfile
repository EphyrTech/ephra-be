FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Install Python dependencies using uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Install development tools using uv
RUN uv pip install --system black isort pylint mypy pytest pytest-cov

# Create upload directory
RUN mkdir -p uploads

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
