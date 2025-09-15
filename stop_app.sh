#!/bin/bash

# SendFix Application Stop Script

echo "=== Stopping SendFix Application ==="

# Stop all instances
echo "Terminating processes gracefully..."
pkill -f "sendfix_web_multi.py" 2>/dev/null
pkill -f "gunicorn.*wsgi:app" 2>/dev/null
pkill -f "python.*sendfix" 2>/dev/null

sleep 3

# Force kill if still running
echo "Force killing any remaining processes..."
pkill -9 -f "sendfix_web_multi.py" 2>/dev/null
pkill -9 -f "gunicorn.*wsgi:app" 2>/dev/null
pkill -9 -f "python.*sendfix" 2>/dev/null

sleep 1

# Verify all stopped
if pgrep -f "sendfix_web_multi.py\|gunicorn.*wsgi:app\|python.*sendfix" > /dev/null; then
    echo "Warning: Some processes may still be running:"
    pgrep -f "sendfix_web_multi.py\|gunicorn.*wsgi:app\|python.*sendfix" -l
    echo "You may need to kill them manually"
else
    echo "All SendFix processes stopped successfully"
fi