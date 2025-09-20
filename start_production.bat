@echo off
REM Production startup script for SendFix Web Application (Windows)

echo Starting SendFix Web Application in Production Mode...

REM Create necessary directories
if not exist logs mkdir logs
if not exist store mkdir store

REM Check if virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Start with Gunicorn (Production WSGI Server)
echo Starting Gunicorn server...
gunicorn --config gunicorn_config.py wsgi:application

echo SendFix Web Application started successfully!
echo Access at: http://localhost:5001
pause