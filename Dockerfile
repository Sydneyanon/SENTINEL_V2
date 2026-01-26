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

# Stage 1: Core numeric/ML build dependencies (order matters)
RUN pip3 install --no-cache-dir --prefer-binary numpy>=1.26.0 Cython scipy

# Stage 2: hdbscan (needs numpy/scipy first, often needs compilation)
RUN pip3 install --no-cache-dir --prefer-binary hdbscan

# Stage 3: Sentence embeddings (heavy download, ~400MB model)
RUN pip3 install --no-cache-dir --prefer-binary sentence-transformers>=2.2.2

# Stage 4: BERTopic (needs hdbscan + sentence-transformers)
RUN pip3 install --no-cache-dir --prefer-binary bertopic>=0.15.0

# Stage 5: All remaining dependencies
RUN pip3 install --no-cache-dir --prefer-binary -r requirements.txt

# Stage 6: Pre-download sentence-transformers model (bake into image)
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Verify ML imports work (fail build early if broken)
RUN python3 -c "import hdbscan; import bertopic; import sentence_transformers; print('ML imports OK')"

# Copy application code
COPY . /app/

# Expose port for FastAPI
EXPOSE 8000

# Default command from Procfile
CMD ["python", "main.py"]
