#!/bin/bash

# SendFix Application Restart Script

echo "=== Restarting SendFix Application ==="

# Stop application
echo "Stopping application..."
pkill -f "sendfix_web_multi.py" 2>/dev/null
pkill -f "gunicorn.*wsgi:app" 2>/dev/null
sleep 2

# Force kill if still running
echo "Ensuring all processes are stopped..."
pkill -9 -f "sendfix_web_multi.py" 2>/dev/null
pkill -9 -f "gunicorn.*wsgi:app" 2>/dev/null
pkill -9 -f "python.*sendfix" 2>/dev/null
sleep 2

# Check if any processes still running
if pgrep -f "sendfix_web_multi.py\|gunicorn.*wsgi:app" > /dev/null; then
    echo "Warning: Some processes may still be running"
    echo "Running processes:"
    pgrep -f "sendfix_web_multi.py\|gunicorn.*wsgi:app" -l
    echo "Please stop manually if needed"
else
    echo "All processes stopped successfully"
fi

# Start application
echo "Starting application..."
if [ -f "start_production.sh" ]; then
    echo "Starting in production mode..."
    ./start_production.sh
else
    echo "Starting in development mode..."
    python3 sendfix_web_multi.py &
fi

echo "Application restarted successfully"
echo "Access at: http://localhost:5001"