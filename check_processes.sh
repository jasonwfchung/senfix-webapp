#!/bin/bash

# SendFix Process Checker Script

echo "=== SendFix Process Status ==="

# Check for running processes
PROCESSES=$(pgrep -f "sendfix_web_multi.py|gunicorn.*wsgi:app|python.*sendfix" -l)

if [ -z "$PROCESSES" ]; then
    echo "No SendFix processes running"
else
    echo "Running SendFix processes:"
    echo "$PROCESSES"
    echo ""
    echo "To kill all processes, run:"
    echo "pkill -9 -f 'sendfix_web_multi.py|gunicorn.*wsgi:app|python.*sendfix'"
fi

# Check port usage
echo ""
echo "Port 5001 usage:"
netstat -tlnp 2>/dev/null | grep :5001 || echo "Port 5001 is free"