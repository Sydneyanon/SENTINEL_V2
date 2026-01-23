# Ralph Autonomous Loop - Railway Deployment
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
    git \
    jq \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies FIRST (before copying code)
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir \
        anthropic==0.40.0 \
        asyncpg \
        python-dotenv

# Verify anthropic is installed
RUN python3 -c "import anthropic; print(f'✓ Anthropic {anthropic.__version__} installed')" || \
    (echo "ERROR: anthropic package not installed" && exit 1)

# Copy entire project
WORKDIR /app
COPY . /app/

# Install any additional requirements if they exist
RUN if [ -f /app/ralph/requirements.txt ]; then \
        pip3 install --no-cache-dir -r /app/ralph/requirements.txt; \
    fi

# Make script executable
RUN chmod +x /app/ralph/ralph.sh /app/ralph/ralph_api.py

# Verify Python script can import anthropic
RUN python3 -c "import sys; sys.path.insert(0, '/app/ralph'); from anthropic import Anthropic; print('✓ Import test passed')"

# Default command: run Ralph with Python API, 10 iterations
CMD ["bash", "/app/ralph/ralph.sh", "--tool", "api", "10"]
