#!/usr/bin/env bash
# sync-push.sh — commit and push Odysseus data to the sync repo.
# Run at the end of a work session before switching machines.
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

git add -A
if git diff --cached --quiet; then
  echo "Nothing to sync — data is up to date."
  exit 0
fi

MSG="sync $(hostname -s) $(date '+%Y-%m-%d %H:%M')"
git commit -m "$MSG"
git push
echo "Pushed: $MSG"
