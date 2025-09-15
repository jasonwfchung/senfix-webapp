#!/bin/bash

# Production startup script for SendFix Web Application

echo "Starting SendFix Web Application in Production Mode..."

# Create necessary directories
mkdir -p logs store

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start with Gunicorn (Production WSGI Server)
echo "Starting Gunicorn server..."
gunicorn --config gunicorn_config.py wsgi:application

echo "SendFix Web Application started successfully!"
echo "Access at: http://localhost:5001"