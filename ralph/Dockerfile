# Ralph Autonomous Loop - Railway Deployment
FROM node:20-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    bash \
    git \
    jq \
    python3 \
    python3-pip \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install Python dependencies for metrics collection
WORKDIR /app/ralph
COPY ralph/requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt || echo "No requirements.txt found"

# Copy Ralph files
COPY ralph/ ./

# Make script executable
RUN chmod +x ralph.sh

# Set working directory to project root for git operations
WORKDIR /app
COPY . .

# Default command: run Ralph with Claude tool, 10 iterations
CMD ["bash", "/app/ralph/ralph.sh", "--tool", "claude", "10"]
