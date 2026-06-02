#!/usr/bin/env bash
# setup-server.sh — Mac Studio: install deps, configure server mode, start Odysseus.
# Run once after cloning. Re-running is safe (idempotent for the .env step).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "==> Checking Ollama..."
if ! command -v ollama &>/dev/null; then
  echo "ERROR: Ollama is not installed. Install from https://ollama.com and re-run."
  exit 1
fi

# Ensure Ollama listens on loopback only (default). Never bind 0.0.0.0 for Ollama.
if ! pgrep -x ollama &>/dev/null; then
  echo "==> Starting Ollama in the background..."
  OLLAMA_HOST=127.0.0.1:11434 ollama serve &>/dev/null &
  sleep 2
fi

echo "==> Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "==> Configuring .env (server mode)..."
if [ ! -f .env ]; then
  cp .env.server.example .env
  # Generate a random key and substitute the placeholder.
  KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  sed -i '' "s/replace_with_a_strong_random_token/$KEY/" .env
  echo ""
  echo "  Created .env from .env.server.example."
  echo "  INFERENCE_SERVER_KEY has been auto-generated:"
  echo ""
  echo "    $KEY"
  echo ""
  echo "  Copy this key to REMOTE_SERVER_KEY in the Windows .env before starting."
else
  echo "  .env already exists — skipping (edit manually if needed)."
fi

echo "==> Starting Odysseus in server mode on 0.0.0.0:7000..."
echo "    Press Ctrl-C to stop."
echo ""
uvicorn app:app --host 0.0.0.0 --port 7000
