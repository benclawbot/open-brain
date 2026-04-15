#!/bin/bash
set -e

echo "Starting Open Brain..."

# Load environment from .env if present (compose env vars are already injected)
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Set defaults
export DB_HOST=${DB_HOST:-postgres}
export DB_PORT=${DB_PORT:-5432}
export DB_NAME=${DB_NAME:-openbrain}
export DB_USER=${DB_USER:-postgres}
export DB_PASSWORD=${DB_PASSWORD:-openbrain}

# Check if database needs setup
echo "Checking database..."
if python scripts/check_db.py; then
  echo "Database already configured."
else
  CHECK_STATUS=$?
  if [ "$CHECK_STATUS" -eq 1 ]; then
    echo "Database needs setup. Running setup..."
    python scripts/setup_db.py
  else
    echo "Database check failed (exit $CHECK_STATUS)."
    exit "$CHECK_STATUS"
  fi
fi

# Start the application
echo "Starting application..."
exec "$@"
