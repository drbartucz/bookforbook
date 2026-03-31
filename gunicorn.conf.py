# Gunicorn configuration for BookForBook
# Used by the Procfile: gunicorn config.wsgi:application -c gunicorn.conf.py

import multiprocessing

# Railway sets PORT; bind is handled via --bind in Procfile
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 120
keepalive = 5
loglevel = "info"
accesslog = "-"  # stdout
errorlog = "-"   # stderr
proc_name = "bookforbook"
