FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=true

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3.10-venv \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN uv pip install -r requirements.txt

# Copy agent code
COPY . /app/cloud/
COPY ../agent-skills/ /app/agent-skills/
COPY ../.claude/skills/ /app/.claude/skills/
COPY ../topology.yaml /app/topology.yaml

# Create vault mount point
RUN mkdir -p /vault

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python3 -c "import json; print('ok')" || exit 1

# Default command
CMD ["uv", "run", "cloud/agent.py", "--vault-path", "/vault"]
