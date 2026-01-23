# Ralph Autonomous Loop - Railway Deployment
FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    bash \
    git \
    jq \
    postgresql-client \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY ralph/requirements.txt /app/ralph/
RUN pip3 install --no-cache-dir \
    anthropic \
    asyncpg \
    python-dotenv \
    && pip3 install --no-cache-dir -r /app/ralph/requirements.txt 2>/dev/null || echo "Optional requirements skipped"

# Copy entire project
COPY . /app/

# Make script executable
RUN chmod +x /app/ralph/ralph.sh

# Set working directory
WORKDIR /app

# Default command: run Ralph with Python API, 10 iterations
CMD ["bash", "/app/ralph/ralph.sh", "--tool", "api", "10"]
