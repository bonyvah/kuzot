#!/bin/sh
set -e

case "$1" in
  uvicorn)
    echo "⏳ Running migrations..."
    alembic upgrade head   # the venv is on PATH; uv run would try to re-sync it
    echo "✅ Migrations done."
    ;;
esac

exec "$@"