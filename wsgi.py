#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""

from sendfix_web_multi import app, socketio

if __name__ == "__main__":
    # For production, use gunicorn instead of this
    socketio.run(app, host='0.0.0.0', port=5001)
else:
    # This is what gunicorn will use
    application = app