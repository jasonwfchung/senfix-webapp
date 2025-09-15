#!/usr/bin/env python3

# Gunicorn configuration for SendFix Web Application

# Server socket
bind = "127.0.0.1:5001"
backlog = 2048

# Worker processes - Use 1 worker for Flask-SocketIO
workers = 1
worker_class = "gevent"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "sendfix_webapp"

# Daemon mode
daemon = False
# pidfile = "sendfix_webapp.pid"  # Disabled for development

# User and group (commented out for local development)
# user = "sendfix"
# group = "sendfix"

# Preload application - Disabled for Flask-SocketIO
preload_app = False

# Enable stats
statsd_host = None