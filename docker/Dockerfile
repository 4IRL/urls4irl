# syntax=docker/dockerfile:1.5

# ============================================
# Builder Stage - Install dependencies
# ============================================
FROM python:3.11-slim-bookworm AS builder

WORKDIR /code/u4i

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements/requirements-prod.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m venv /code/venv \
    && . /code/venv/bin/activate \
    && pip install --upgrade pip \
    && pip install --no-compile -r requirements-prod.txt \
    && find /code/venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /code/venv -type f -name '*.pyc' -delete

# ============================================
# Runtime Stage - Final production image
# ============================================
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/4IRL/urls4irl"

ENV FLASK_APP=run \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOG_DIR=/app/volume/logs

WORKDIR /code/u4i

# Install ONLY runtime dependencies and create user
RUN set -ex \
    && addgroup --system --gid 1001 u4i-host-group \
    && adduser --system --uid 1001 --gid 1001 --no-create-home u4i-host \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
	wget \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy virtual environment from builder
COPY --from=builder --chown=u4i-host:u4i-host-group /code/venv /code/venv

# Copy application code
COPY --chown=u4i-host:u4i-host-group docker/startup-flask.sh ./
COPY --chown=u4i-host:u4i-host-group run.py ./
COPY --chown=u4i-host:u4i-host-group src/ ./src/
COPY --chown=u4i-host:u4i-host-group migrations/ ./migrations/

# Create log directory and set permissions
RUN mkdir -p /app/volume/logs \
    && chmod -R 775 /code /app/volume/logs \
    && chown -R u4i-host:u4i-host-group /code /app/volume/logs \
    && chmod +x /code/u4i/startup-flask.sh

USER u4i-host

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

