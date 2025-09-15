# Production Deployment Guide

## Deployment Options

### Option 1: Simple File Copy (Basic)
```bash
# 1. Create application directory on production server
sudo mkdir -p /opt/sendfix-webapp
sudo chown $USER:$USER /opt/sendfix-webapp

# 2. Copy all files
scp -r webapp/* user@production-server:/opt/sendfix-webapp/

# 3. Install dependencies on production server
ssh user@production-server
cd /opt/sendfix-webapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Run application
python sendfix_web_multi.py
```

### Option 2: Production Web Server (Recommended)

#### Using Gunicorn + Nginx
```bash
# 1. Install Gunicorn
pip install gunicorn eventlet

# 2. Create Gunicorn config
# File: gunicorn_config.py
bind = "127.0.0.1:5001"
workers = 4
worker_class = "eventlet"
worker_connections = 1000
timeout = 30
keepalive = 2
```

#### Nginx Configuration
```nginx
# File: /etc/nginx/sites-available/sendfix
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### Option 3: Systemd Service (Production)

#### Create Service File
```bash
# File: /etc/systemd/system/sendfix-webapp.service
[Unit]
Description=SendFix Multi-Session Web Application
After=network.target

[Service]
Type=simple
User=sendfix
Group=sendfix
WorkingDirectory=/opt/sendfix-webapp
Environment=PATH=/opt/sendfix-webapp/venv/bin
ExecStart=/opt/sendfix-webapp/venv/bin/gunicorn --config gunicorn_config.py sendfix_web_multi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable sendfix-webapp
sudo systemctl start sendfix-webapp
sudo systemctl status sendfix-webapp
```

### Option 4: Docker Deployment

#### Create Dockerfile
```dockerfile
# File: Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create non-root user
RUN useradd -m -u 1000 sendfix && chown -R sendfix:sendfix /app
USER sendfix

# Expose port
EXPOSE 5001

# Run application
CMD ["gunicorn", "--config", "gunicorn_config.py", "sendfix_web_multi:app"]
```

#### Docker Compose
```yaml
# File: docker-compose.yml
version: '3.8'

services:
  sendfix-webapp:
    build: .
    ports:
      - "5001:5001"
    volumes:
      - ./logs:/app/logs
      - ./store:/app/store
    environment:
      - FLASK_ENV=production
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - sendfix-webapp
    restart: unless-stopped
```

## Production Configuration

### 1. Update Configuration Files

#### Production sendfix.cfg
```ini
[DEFAULT]
ServerIP=production-fix-server.com
Port=5731
FixVersion=FIX.4.2
SenderCompId=PROD_SENDER
TargetCompId=PROD_TARGET
HeartbeatInterval=30
```

#### Production multi_session_config.json
```json
{
  "sessions": [
    {
      "name": "Production Session",
      "server_ip": "production-fix-server.com",
      "port": 5731,
      "fix_version": "FIX.4.2",
      "sender_comp_id": "PROD_SENDER",
      "target_comp_id": "PROD_TARGET",
      "heartbeat_interval": 30
    }
  ]
}
```

### 2. Security Hardening

#### Environment Variables
```bash
# File: .env
FLASK_SECRET_KEY=your-super-secret-production-key
FIX_SERVER_HOST=production-fix-server.com
FIX_SERVER_PORT=5731
```

#### Update Application for Production
```python
# Add to sendfix_web_multi.py
import os
from dotenv import load_dotenv

load_dotenv()

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback-key')
```

### 3. Monitoring and Logging

#### Log Configuration
```python
# Add to sendfix_web_multi.py
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler('logs/sendfix.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
```

## Step-by-Step Production Deployment

### Method 1: Simple Deployment
```bash
# 1. Prepare production server
sudo apt update && sudo apt install python3 python3-pip python3-venv nginx

# 2. Create application user
sudo useradd -m -s /bin/bash sendfix
sudo mkdir -p /opt/sendfix-webapp
sudo chown sendfix:sendfix /opt/sendfix-webapp

# 3. Copy files
scp -r webapp/* sendfix@your-server:/opt/sendfix-webapp/

# 4. Setup application
sudo -u sendfix bash
cd /opt/sendfix-webapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn eventlet

# 5. Test application
python sendfix_web_multi.py  # Test locally first

# 6. Setup production service (as root)
sudo cp sendfix-webapp.service /etc/systemd/system/
sudo systemctl enable sendfix-webapp
sudo systemctl start sendfix-webapp
```

### Method 2: Docker Deployment
```bash
# 1. Copy files to server
scp -r webapp/* user@your-server:/opt/sendfix-webapp/

# 2. Build and run
ssh user@your-server
cd /opt/sendfix-webapp
docker-compose up -d

# 3. Check status
docker-compose ps
docker-compose logs -f sendfix-webapp
```

## Production Checklist

### Security
- [ ] Change default secret keys
- [ ] Use environment variables for sensitive data
- [ ] Enable HTTPS with SSL certificates
- [ ] Configure firewall rules
- [ ] Set up user authentication if needed

### Performance
- [ ] Use Gunicorn with multiple workers
- [ ] Configure Nginx reverse proxy
- [ ] Set up load balancing if needed
- [ ] Configure caching headers

### Monitoring
- [ ] Set up application logging
- [ ] Configure log rotation
- [ ] Monitor system resources
- [ ] Set up health checks
- [ ] Configure alerting

### Backup
- [ ] Backup configuration files
- [ ] Backup session state data
- [ ] Set up automated backups
- [ ] Test restore procedures

## Troubleshooting

### Common Issues
1. **Port conflicts**: Change port in configuration
2. **Permission errors**: Check file ownership and permissions
3. **WebSocket issues**: Ensure proxy configuration supports WebSockets
4. **FIX connection failures**: Verify network connectivity and credentials

### Debug Commands
```bash
# Check service status
sudo systemctl status sendfix-webapp

# View logs
sudo journalctl -u sendfix-webapp -f

# Test connectivity
telnet fix-server-ip 5731

# Check port usage
sudo netstat -tlnp | grep 5001
```

## Recommended Production Setup

For most production environments, use **Option 2 (Gunicorn + Nginx)** with **Option 3 (Systemd Service)**:

1. **Reliable**: Automatic restart on failure
2. **Scalable**: Multiple worker processes
3. **Secure**: Nginx handles SSL and security headers
4. **Maintainable**: Standard Linux service management