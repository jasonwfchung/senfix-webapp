#!/bin/bash

# SendFix Day-End Reset Script with Backup
# Backs up current session data and resets for next trading day

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backup_$DATE"

echo "=== SendFix Day-End Reset with Backup ==="
echo "Date: $(date)"
echo "Backup directory: $BACKUP_DIR"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Stop web application if running
echo "Stopping web application..."
pkill -f "sendfix_web_multi.py" 2>/dev/null
pkill -f "gunicorn.*wsgi:app" 2>/dev/null
sleep 3

# Backup current session data
echo "Creating backup of session data..."

if [ -d "store" ]; then
    cp -r store "$BACKUP_DIR/"
    echo "Store backed up"
fi

if [ -d "log" ]; then
    cp -r log "$BACKUP_DIR/"
    echo "Logs backed up"
fi

if [ -f "session_state.json" ]; then
    cp session_state.json "$BACKUP_DIR/"
    echo "Session state backed up"
fi

if [ -f "sendfix_quickfix.log" ]; then
    cp sendfix_quickfix.log "$BACKUP_DIR/"
    echo "Application log backed up"
fi

# Clear QuickFIX store
echo "Clearing QuickFIX store..."
rm -rf store/*
mkdir -p store

# Clear QuickFIX logs
echo "Clearing QuickFIX logs..."
rm -rf log/*
mkdir -p log

# Clear application logs
echo "Clearing application logs..."
rm -rf logs/*
mkdir -p logs

# Remove session state
echo "Resetting session state..."
rm -f session_state.json
rm -f sendfix_quickfix.log
rm -f quickfix_client.cfg

# Clean temporary files
echo "Cleaning temporary files..."
rm -f *.tmp
rm -f /tmp/fix_orders_*.txt

# Compress backup
echo "Compressing backup..."
tar -czf "${BACKUP_DIR}.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo ""
echo "=== Day-End Reset Complete ==="
echo "✓ Session data backed up to: ${BACKUP_DIR}.tar.gz"
echo "✓ QuickFIX store cleared"
echo "✓ All logs cleared"
echo "✓ Session state reset"
echo "✓ Sequence numbers will start from 1"
echo ""
echo "Ready for next trading day!"
echo "Start with: ./start_production.sh"