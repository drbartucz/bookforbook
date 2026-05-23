#!/bin/bash
set -e

# Collect static files (runs here because Railway env vars aren't available during Docker build)
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

# Start qcluster worker in background
python manage.py qcluster &
QCLUSTER_PID=$!

# Start gunicorn in foreground (Railway health checks depend on this)
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:"${PORT:-8000}" \
    --workers 2 \
    --threads 2 \
    --worker-class gthread \
    --max-requests 1000 \
    --max-requests-jitter 100
