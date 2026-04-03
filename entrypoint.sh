#!/usr/bin/env bash
set -e

# If .env does not exist, run the interactive setup wizard
if [ ! -f ".env" ]; then
  echo "No .env found — launching setup wizard..."
  python -m app.setup_wizard
fi

# Load .env into environment
set -a
source .env
set +a

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
