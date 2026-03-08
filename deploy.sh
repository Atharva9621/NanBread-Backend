#!/bin/bash
# deploy.sh
# Run this for every redeployment.
# Pulls latest code, rebuilds image, restarts container.
#
# Usage:
#   ./deploy.sh

set -e

CONTAINER_NAME="nanbread"
IMAGE_NAME="nanbread"

echo "Pulling latest code..."
git pull

echo "Rebuilding image..."
docker build -t $IMAGE_NAME .

echo "Stopping old container..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker wait $CONTAINER_NAME 2>/dev/null || true   # wait until fully stopped
docker rm   $CONTAINER_NAME 2>/dev/null || true

echo "Starting new container..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p 8080:8080 \
  --env-file .env \
  $IMAGE_NAME

echo "Done. Logs:"
docker logs --tail 20 $CONTAINER_NAME