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

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Find and symlink claude binary (npm sometimes doesn't create bin link properly)
RUN CLAUDE_BIN=$(find /usr/local/lib/node_modules/@anthropic-ai/claude-code -name "claude" -type f 2>/dev/null | head -1) && \
    if [ -n "$CLAUDE_BIN" ]; then \
        echo "Found Claude at: $CLAUDE_BIN"; \
        ln -sf "$CLAUDE_BIN" /usr/local/bin/claude; \
        chmod +x /usr/local/bin/claude; \
    else \
        echo "ERROR: Claude binary not found after npm install"; \
        exit 1; \
    fi

# Verify claude command works
RUN claude --version || (echo "ERROR: claude command failed" && exit 1)

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
