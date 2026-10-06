#!/bin/sh
set -e

case "$1" in
  uvicorn)
    echo "⏳ Running migrations..."
    uv run alembic upgrade head
    echo "✅ Migrations done."
    ;;
esac

exec "$@"