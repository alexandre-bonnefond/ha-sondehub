#!/usr/bin/env bash
# Copy the integration (and the blueprint) to a Home Assistant host over SSH.
#
# Needs SSH access to the HA config directory, e.g. the "Terminal & SSH" or
# "Advanced SSH & Web Terminal" add-on with your public key configured.
#
# Usage: scripts/deploy.sh [user@host] [--restart]
#   user@host   defaults to $HA_SSH or root@homeassistant.local
#   --restart   check the configuration and restart Home Assistant Core
# Env:
#   HA_SSH_PORT    SSH port (default 22)
#   HA_CONFIG_DIR  config directory on the host (default /config)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${HA_SSH:-root@homeassistant.local}"
PORT="${HA_SSH_PORT:-22}"
CONFIG_DIR="${HA_CONFIG_DIR:-/config}"
RESTART=0

for arg in "$@"; do
  case "$arg" in
    --restart) RESTART=1 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) HOST="$arg" ;;
  esac
done

run() { ssh -p "$PORT" "$HOST" "$@"; }

echo "Copying custom_components/sondehub to $HOST:$CONFIG_DIR/custom_components/"
# tar over ssh works with every SSH add-on (some lack SFTP, which scp now needs).
tar -C "$ROOT/custom_components" --exclude=__pycache__ -cf - sondehub \
  | run "mkdir -p '$CONFIG_DIR/custom_components' \
         && rm -rf '$CONFIG_DIR/custom_components/sondehub' \
         && tar -C '$CONFIG_DIR/custom_components' -xf -"

echo "Copying blueprint to $HOST:$CONFIG_DIR/blueprints/automation/sondehub/"
tar -C "$ROOT/blueprints/automation" -cf - sondehub \
  | run "mkdir -p '$CONFIG_DIR/blueprints/automation' \
         && tar -C '$CONFIG_DIR/blueprints/automation' -xf -"

if [[ $RESTART -eq 1 ]]; then
  echo "Checking configuration and restarting Home Assistant Core..."
  run "ha core check && ha core restart"
else
  echo "Done. Restart Home Assistant to load the new version."
fi
