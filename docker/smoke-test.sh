#!/usr/bin/env bash
set -e

IMAGE_NAME=$1
ENV_VARS=$2

echo "🚀 Starting smoke test for $IMAGE_NAME..."

# Run the container (using Docker's internal healthcheck)
CONTAINER_ID=$(docker run -d $ENV_VARS --name "smoke_test" "$IMAGE_NAME")

# Cleanup trap
trap 'echo "🧹 Cleaning up..."; docker stop $CONTAINER_ID > /dev/null && docker rm $CONTAINER_ID > /dev/null' EXIT

echo "Waiting for Docker Healthcheck status..."

# Poll Docker for the health status
MAX_RETRIES=15
for i in $(seq 1 $MAX_RETRIES); do
  # Get the status: starting, healthy, or unhealthy
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID")

  if [ "$STATUS" == "healthy" ]; then
    echo "✅ Smoke test PASSED ($STATUS)"
    exit 0
  fi

  if [ "$STATUS" == "unhealthy" ]; then
    echo "❌ Smoke test FAILED ($STATUS)"
    docker logs "$CONTAINER_ID"
    exit 1
  fi

  echo "Attempt $i/$MAX_RETRIES: Status is '$STATUS'. Retrying in 5s..."
  sleep 5
done

echo "❌ Smoke test TIMED OUT"
docker logs "$CONTAINER_ID"
exit 1
