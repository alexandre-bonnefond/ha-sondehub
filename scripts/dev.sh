#!/usr/bin/env bash
# Run a throwaway Home Assistant in Docker with this integration mounted.
# Open http://localhost:8123, create a user, then add "SondeHub Radiosondes".
#
# Config is kept in the Docker volume "ha-sondehub-dev" between runs;
# `docker volume rm ha-sondehub-dev` resets it. Ctrl+C stops the container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}"
PORT="${HA_PORT:-8123}"

exec docker run --rm -it --name ha-sondehub-dev \
  --dns 1.1.1.1 \
  -p "127.0.0.1:$PORT:8123" \
  -v ha-sondehub-dev:/config \
  -v "$ROOT/custom_components/sondehub:/config/custom_components/sondehub:ro" \
  -v "$ROOT/blueprints/automation/sondehub:/config/blueprints/automation/sondehub:ro" \
  "$IMAGE"
