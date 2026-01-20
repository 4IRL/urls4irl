#!/usr/bin/env bash
set -e

IMAGE_NAME=$1

echo "🚀 Starting smoke test for $IMAGE_NAME..."
ENV_VARS="-e SECRET_KEY=ABC123456"

# Run the container (using Docker's internal healthcheck)
echo "Running container..."
if [[ "$IMAGE_NAME" == *"u4i-prod"* ]]; then
    CONTAINER_ID=$(docker run -d \
        --entrypoint bash \
        -e DEV_SERVER=true \
        -e POSTGRES_USER=bob \
        -e POSTGRES_DB=test \
        -e POSTGRES_TEST_DB=test \
        -e POSTGRES_PASSWORD=test \
        -e IS_DOCKER=true \
        --name "smoke_test" \
        "$IMAGE_NAME" \
        -c ". /code/venv/bin/activate && flask run --host=0.0.0.0 --port=5000"
    )
else
    CONTAINER_ID=$(docker run -d \
      -e POSTGRES_USER=bob \
      -e POSTGRES_DB=test \
      -e POSTGRES_PASSWORD=test \
      --name "smoke_test" \
      "$IMAGE_NAME"
    )
fi

echo "Container ID: $CONTAINER_ID"

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
