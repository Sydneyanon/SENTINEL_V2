# SENTINEL V2 - Main Application Dockerfile
# Includes build dependencies for ML packages (bertopic, hdbscan, xgboost)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install system dependencies including build tools for ML packages
RUN apt-get update && apt-get install -y \
    bash \
    git \
    postgresql-client \
    curl \
    build-essential \
    python3-dev \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and install dependencies
WORKDIR /app
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Expose port for FastAPI
EXPOSE 8000

# Default command from Procfile
CMD ["python", "main.py"]
