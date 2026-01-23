# Ralph Autonomous Loop - Railway Deployment
FROM python:3.11-slim

# Disable Railway's auto-detection by removing any Python markers
ENV NIXPACKS_NO_MUSL=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
    git \
    jq \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly (NO virtualenv)
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir \
        anthropic==0.40.0 \
        asyncpg \
        python-dotenv

# Verify anthropic is installed in system Python
RUN python3 -c "import anthropic; print(f'✓ Anthropic {anthropic.__version__} installed at {anthropic.__file__}')"

# Copy entire project
WORKDIR /app
COPY . /app/

# Make scripts executable
RUN chmod +x /app/ralph/ralph.sh /app/ralph/ralph_api.py

# Default command: run Ralph with bash wrapper (handles 10 iterations)
CMD ["bash", "/app/ralph/ralph.sh", "--tool", "api", "10"]
