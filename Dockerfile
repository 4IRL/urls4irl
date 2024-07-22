# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/4IRL/urls4irl"

# Some environment variable handling
ENV FLASK_APP=run
ENV PYTHONUNBEFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

# Use code as working directory
WORKDIR /code

# Create non-root user, update packages, clean up
RUN set -ex \
	&& addgroup --system --gid 1001 u4i-host-group \
	&& adduser --system --uid 1001 --gid 1001 --no-create-home u4i-host \
	&& apt-get update \
	&& apt-get -y install libpq-dev gcc \
	&& apt-get upgrade -y \
	&& apt-get autoremove -y \
	&& apt-get clean -y \
	&& rm -rf /var/lib/apt/lists/*

# Change ownership to newly created user
RUN chown -R u4i-host:u4i-host-group /code

# Create a non-root user
USER u4i-host

# Install production level requirements
COPY requirements-prod.txt ./
RUN python3 -m venv venv \
	&& . venv/bin/activate \
	&& pip install -r requirements-prod.txt --no-cache-dir

# Copy files needed
COPY run.py ./
COPY src/ ./src/
COPY migrations/ ./migrations/

# Expose a port to access the container
EXPOSE 5000
