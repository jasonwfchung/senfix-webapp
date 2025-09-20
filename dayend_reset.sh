#!/bin/bash

# SendFix Day-End Reset Script
# Clears QuickFIX store and resets sequence numbers to 1

echo "=== SendFix Day-End Reset ==="
echo "Starting day-end cleanup process..."

# Stop web application if running
echo "Stopping web application..."
pkill -f "sendfix_web_multi.py" 2>/dev/null
pkill -f "gunicorn.*wsgi:app" 2>/dev/null
sleep 2

# Clear QuickFIX store directory
if [ -d "store" ]; then
    echo "Clearing QuickFIX store directory..."
    rm -rf store/*
    echo "Store directory cleared"
else
    echo "Store directory not found, creating..."
    mkdir -p store
fi

# Clear QuickFIX log directory
if [ -d "log" ]; then
    echo "Clearing QuickFIX log directory..."
    rm -rf log/*
    echo "Log directory cleared"
else
    echo "Log directory not found, creating..."
    mkdir -p log
fi

# Clear application logs directory
if [ -d "logs" ]; then
    echo "Clearing application logs..."
    rm -rf logs/*
    echo "Application logs cleared"
else
    echo "Logs directory not found, creating..."
    mkdir -p logs
fi

# Remove session state files
echo "Removing session state files..."
rm -f session_state.json
rm -f sendfix_quickfix.log
rm -f quickfix_client.cfg

# Remove any temporary files
echo "Cleaning temporary files..."
rm -f *.tmp
rm -f /tmp/fix_orders_*.txt

echo ""
echo "=== Day-End Reset Complete ==="
echo "- QuickFIX store cleared"
echo "- Log files cleared" 
echo "- Session state reset"
echo "- Sequence numbers will start from 1"
echo ""
echo "You can now start the application for the next trading day."
echo "Run: ./start_production.sh or python3 sendfix_web_multi.py"