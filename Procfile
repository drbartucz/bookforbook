web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --worker-class gthread --max-requests 1000 --max-requests-jitter 100
worker: python manage.py qcluster
