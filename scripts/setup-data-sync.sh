#!/usr/bin/env bash
# setup-data-sync.sh — one-time setup: init the data/ git repo and link it
# to a private GitHub sync repo.
#
# Usage:
#   scripts/setup-data-sync.sh https://github.com/<you>/odysseus-data.git
#
# Create the private repo first:
#   gh repo create odysseus-data --private
set -euo pipefail

REMOTE="${1:-}"
DATA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/data"

if [ -z "$REMOTE" ]; then
  echo "Usage: $0 <git-remote-url>"
  echo "Example: $0 https://github.com/michalglomsky/odysseus-data.git"
  echo ""
  echo "Create the private repo first with: gh repo create odysseus-data --private"
  exit 1
fi

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

if [ ! -d .git ]; then
  git init -b main
  echo "Initialized git repo in $DATA_DIR"
fi

if ! git remote get-url origin &>/dev/null; then
  git remote add origin "$REMOTE"
  echo "Remote set to $REMOTE"
else
  echo "Remote already set: $(git remote get-url origin)"
fi

# Pull existing data if the remote already has commits (cloning on second machine).
if git ls-remote --exit-code origin main &>/dev/null 2>&1; then
  echo "Remote has data — pulling..."
  git fetch origin main
  git reset --hard origin/main
else
  # First machine: do an initial push.
  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "initial data snapshot $(date '+%Y-%m-%d')"
  else
    git commit --allow-empty -m "initial commit"
  fi
  git push -u origin main
  echo "Initial snapshot pushed."
fi

echo ""
echo "Setup complete. Workflow:"
echo "  End of session:   scripts/sync-push.sh"
echo "  Start of session: scripts/sync-pull.sh"
