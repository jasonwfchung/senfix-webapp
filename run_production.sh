#!/bin/bash
cd /mnt/c/app/WSL_Project/webapp
export PATH="/mnt/c/app/WSL_Project/webapp/venv/bin:$PATH"
gunicorn -c gunicorn_config.py wsgi:app