# Ralph Autonomous Loop - Railway Deployment
FROM node:20-slim

# Set PATH to include npm global bins
ENV PATH="/usr/local/bin:$PATH"

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

# Install Claude Code CLI and ensure it's in PATH
RUN npm install -g @anthropic-ai/claude-code && \
    npm list -g @anthropic-ai/claude-code && \
    ls -la /usr/local/bin/ | grep claude || echo "Claude binary not found" && \
    which claude || echo "Claude not in PATH - checking alternatives" && \
    find /usr/local -name claude -type f 2>/dev/null || true

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
