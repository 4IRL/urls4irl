# syntax=docker/dockerfile:1.5
FROM debian:12-slim
LABEL org.opencontainers.image.source="https://github.com/4IRL/urls4irl/daily-workflow"

# Install system dependencies
ARG RCLONE_VERSION=v1.72.1
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    bash \
    curl \
    jq \
    tar \
    gzip \
    cron \
    wget \
    gnupg \
    lsb-release \
    ca-certificates \
    unzip \
    file \
    procps \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && RCLONE_VERSION=${RCLONE_VERSION} curl -fsSL https://rclone.org/install.sh | bash \
    && unset RCLONE_VERSION \
    && rclone version \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create non-root user for running cron jobs
RUN groupadd --gid 1001 workflow \
    && useradd --uid 1001 --gid workflow --shell /bin/bash --create-home workflow

# Create app directory with proper permissions
WORKDIR /app
RUN mkdir -p /app/workflow_logs \
    && chown -R workflow:workflow /app

# Copy scripts
COPY --chown=workflow:workflow docker/startup-workflow.sh /app/
COPY --chown=workflow:workflow utils/daily-docker.sh /app/
COPY --chown=workflow:workflow utils/backup-database.sh /app/
COPY --chown=workflow:workflow utils/backup-logs.sh /app/
COPY --chown=workflow:workflow utils/remote-object-storage.sh /app/
COPY utils/restricted-curl.sh /usr/bin/restricted_curl

# Copy crontab job
COPY docker/crontab.workflow /tmp/crontab.workflow

# Make scripts executable and replace curl with a restricted version
RUN chmod +x /app/*.sh \
    && chmod +x /usr/bin/restricted_curl \
    && mv /usr/bin/curl /usr/bin/curl.real \
    && ln -s /usr/bin/restricted_curl /usr/bin/curl

# Add healthcheck
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
    CMD pgrep cron || exit 1

# Container runs as root to start cron daemon
# Cron jobs themselves run as 'workflow' user (set via crontab -u)
ENTRYPOINT ["/app/startup-workflow.sh"]
