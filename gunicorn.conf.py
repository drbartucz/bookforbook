# Gunicorn configuration for BookForBook
# Copy this file and set the values for your environment.
# Start with: gunicorn config.wsgi:application -c gunicorn.conf.py

bind = "0.0.0.0:26386"         # port assigned by SureSupport control panel
workers = 2                     # 2 workers is sufficient for shared hosting
timeout = 60                    # kill a worker if it takes longer than 60s
keepalive = 5

accesslog = "/home/bookforbook/private/logs/gunicorn-access.log"
errorlog  = "/home/bookforbook/private/logs/gunicorn-error.log"
loglevel  = "info"

pidfile   = "/tmp/bookforbook.pid"   # used for graceful reloads (kill -HUP)
proc_name = "bookforbook"
