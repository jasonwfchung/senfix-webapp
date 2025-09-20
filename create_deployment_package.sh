#!/bin/bash

# SendFix Production Deployment Package Creator

VERSION=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="sendfix-webapp-${VERSION}"
PACKAGE_DIR="/tmp/${PACKAGE_NAME}"

echo "=== Creating SendFix Deployment Package ==="
echo "Version: ${VERSION}"
echo "Package: ${PACKAGE_NAME}.tgz"

# Create package directory
mkdir -p "${PACKAGE_DIR}"

# Copy application files
echo "Copying application files..."
cp -r templates/ "${PACKAGE_DIR}/"
cp sendfix_web_multi.py "${PACKAGE_DIR}/"
cp multi_fix_client.py "${PACKAGE_DIR}/"
cp quickfix_client.py "${PACKAGE_DIR}/"
cp wsgi.py "${PACKAGE_DIR}/"
cp gunicorn_config.py "${PACKAGE_DIR}/"
cp requirements.txt "${PACKAGE_DIR}/"

# Copy configuration files
echo "Copying configuration files..."
cp multi_session_config.json "${PACKAGE_DIR}/"
cp users.json "${PACKAGE_DIR}/"
cp sendfix.cfg "${PACKAGE_DIR}/"

# Copy scripts
echo "Copying management scripts..."
cp start_production.sh "${PACKAGE_DIR}/"
cp restart_app.sh "${PACKAGE_DIR}/"
cp stop_app.sh "${PACKAGE_DIR}/"
cp dayend_reset.sh "${PACKAGE_DIR}/"
cp dayend_reset_with_backup.sh "${PACKAGE_DIR}/"

# Copy service file
cp sendfix-webapp.service "${PACKAGE_DIR}/"

# Create deployment guide
cat > "${PACKAGE_DIR}/DEPLOYMENT_GUIDE.md" << 'EOF'
# SendFix Web Application - Production Deployment Guide

## Prerequisites
- Linux server (Ubuntu 18.04+ or CentOS 7+)
- Python 3.8+
- QuickFIX library
- Network access to FIX servers

## Installation Steps

### 1. Extract Package
```bash
tar -xzf sendfix-webapp-*.tgz
cd sendfix-webapp-*
```

### 2. Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv build-essential

# CentOS/RHEL
sudo yum install python3 python3-pip gcc gcc-c++ make
```

### 3. Create Application Directory
```bash
sudo mkdir -p /opt/sendfix
sudo cp -r * /opt/sendfix/
sudo chown -R $USER:$USER /opt/sendfix
cd /opt/sendfix
```

### 4. Setup Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure Application
```bash
# Edit configuration files
nano multi_session_config.json  # Update FIX sessions
nano users.json                 # Update user credentials
```

### 6. Setup Systemd Service
```bash
sudo cp sendfix-webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sendfix-webapp
```

### 7. Start Application
```bash
sudo systemctl start sendfix-webapp
sudo systemctl status sendfix-webapp
```

### 8. Configure Firewall
```bash
# Ubuntu
sudo ufw allow 5001/tcp

# CentOS
sudo firewall-cmd --permanent --add-port=5001/tcp
sudo firewall-cmd --reload
```

## Access Application
- URL: http://server-ip:5001
- Default users: admin/admin123, trader1/trader123

## Management Commands
```bash
# Restart application
./restart_app.sh

# Stop application
./stop_app.sh

# Day-end reset
./dayend_reset_with_backup.sh

# View logs
sudo journalctl -u sendfix-webapp -f
```

## Security Notes
- Change default passwords in users.json
- Update SECRET_KEY in sendfix_web_multi.py
- Consider using HTTPS with reverse proxy
- Restrict network access to authorized IPs
EOF

# Create production checklist
cat > "${PACKAGE_DIR}/PRODUCTION_CHECKLIST.md" << 'EOF'
# Production Deployment Checklist

## Pre-Deployment
- [ ] Server meets system requirements
- [ ] Network connectivity to FIX servers verified
- [ ] Firewall rules configured
- [ ] Backup strategy planned

## Security Configuration
- [ ] Changed default passwords in users.json
- [ ] Updated SECRET_KEY in sendfix_web_multi.py
- [ ] Configured proper file permissions
- [ ] Network access restricted to authorized IPs

## Application Configuration
- [ ] Updated multi_session_config.json with production FIX sessions
- [ ] Verified FIX server connectivity
- [ ] Tested user authentication
- [ ] Validated session management

## Testing
- [ ] Application starts successfully
- [ ] Login functionality works
- [ ] FIX sessions connect properly
- [ ] Order sending/receiving tested
- [ ] Configuration management tested
- [ ] Server restart functionality tested

## Monitoring
- [ ] Log monitoring configured
- [ ] System resource monitoring setup
- [ ] Alert mechanisms configured
- [ ] Backup procedures tested

## Documentation
- [ ] User training completed
- [ ] Operations procedures documented
- [ ] Emergency contacts established
- [ ] Escalation procedures defined
EOF

# Make scripts executable
chmod +x "${PACKAGE_DIR}"/*.sh

# Create package
echo "Creating deployment package..."
cd /tmp
tar -czf "${PACKAGE_NAME}.tgz" "${PACKAGE_NAME}"

# Move to current directory
mv "${PACKAGE_NAME}.tgz" "${OLDPWD}/"

# Cleanup
rm -rf "${PACKAGE_DIR}"

echo ""
echo "=== Deployment Package Created ==="
echo "Package: ${PACKAGE_NAME}.tgz"
echo "Size: $(du -h ${PACKAGE_NAME}.tgz | cut -f1)"
echo ""
echo "Next steps:"
echo "1. Transfer ${PACKAGE_NAME}.tgz to production server"
echo "2. Follow DEPLOYMENT_GUIDE.md instructions"
echo "3. Complete PRODUCTION_CHECKLIST.md items"