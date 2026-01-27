# SENTINEL V2 - Main Application Dockerfile
# Python 3.11 for best ML package wheel support (bertopic, hdbscan, xgboost)
FROM python:3.11-slim

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
    pkg-config \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and install dependencies
WORKDIR /app
COPY requirements.txt /app/

# Stage 1: Core numeric dependencies (order matters)
RUN pip3 install --no-cache-dir --prefer-binary numpy>=1.26.0 Cython scipy

# Stage 2: PyTorch CPU-only (no GPU on Railway - saves ~1.5GB)
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Stage 3: hdbscan (needs numpy/scipy)
RUN pip3 install --no-cache-dir --prefer-binary hdbscan

# Stage 4: transformers + sentence-transformers (needs torch)
RUN pip3 install --no-cache-dir --prefer-binary transformers sentence-transformers

# Stage 5: BERTopic (needs hdbscan + sentence-transformers)
RUN pip3 install --no-cache-dir --prefer-binary bertopic>=0.15.0

# Stage 6: All remaining dependencies
RUN pip3 install --no-cache-dir --prefer-binary -r requirements.txt

# Verify ML imports work (fail build early if broken)
RUN python3 -c "import hdbscan; from bertopic import BERTopic; from sentence_transformers import SentenceTransformer; print('ML imports OK')"

# Copy application code
COPY . /app/

# Expose port for FastAPI
EXPOSE 8000

# Default command from Procfile
CMD ["python", "main.py"]
