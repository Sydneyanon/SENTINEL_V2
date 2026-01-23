# Ralph Autonomous Loop - Railway Deployment
# Build: 2026-01-23T19:00 (CRITICAL: git configuration fix)
FROM python:3.11-slim

# Disable Railway's auto-detection by removing any Python markers
ENV NIXPACKS_NO_MUSL=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (CRITICAL: git is required for Ralph to commit)
RUN apt-get update && apt-get install -y \
    bash \
    git \
    jq \
    postgresql-client \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Verify git is installed
RUN git --version

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Verify Claude Code is installed
RUN claude --version || echo "Claude Code installed"

# Install Python dependencies directly (NO virtualenv)
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir \
        anthropic==0.40.0 \
        asyncpg \
        python-dotenv

# Verify anthropic is installed in system Python
RUN python3 -c "import anthropic; print(f'✓ Anthropic {anthropic.__version__} installed at {anthropic.__file__}')"

# Create non-root user (Claude Code CLI won't run --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash ralph && \
    mkdir -p /home/ralph/.cache && \
    chown -R ralph:ralph /home/ralph

# Copy entire project
WORKDIR /app
COPY . /app/

# Make scripts executable and set ownership
RUN chmod +x /app/ralph/ralph.sh /app/ralph/ralph_api.py && \
    chown -R ralph:ralph /app

# Switch to non-root user
USER ralph

# Default command: run Ralph with Claude Code CLI (has Bash/Git/Edit tools for actual execution)
CMD ["bash", "/app/ralph/ralph.sh", "--tool", "claude", "30"]
