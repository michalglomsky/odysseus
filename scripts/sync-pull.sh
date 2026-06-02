#!/usr/bin/env bash
# sync-pull.sh — pull latest Odysseus data before starting a work session.
# Run at the start of a session after switching machines.
#
# First-time setup: run scripts/setup-data-sync.sh
set -euo pipefail

DATA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/data"

if [ ! -d "$DATA_DIR/.git" ]; then
  echo "ERROR: $DATA_DIR is not a git repo."
  echo "Run scripts/setup-data-sync.sh first."
  exit 1
fi

cd "$DATA_DIR"

echo "Pulling latest data..."
git pull --rebase
echo "Done — data is up to date."
