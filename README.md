# SendFix Multi-Session Web Application

Professional web-based FIX protocol trading client with QuickFIX/n engine and multi-session support.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Sessions
Edit `multi_session_config.json` with your FIX server details:
```json
{
  "sessions": [
    {
      "name": "LQNT UAT",
      "server_ip": "hk1qvphxcrt01",
      "port": 5731,
      "fix_version": "FIX.4.2",
      "sender_comp_id": "JCHUNG",
      "target_comp_id": "LQNTHKUAT",
      "heartbeat_interval": 30
    },
    {
      "name": "ASIA TEST",
      "server_ip": "hk1qvphxcrt01",
      "port": 5630,
      "fix_version": "FIX.4.2",
      "sender_comp_id": "ASIATEST5",
      "target_comp_id": "LQNT",
      "heartbeat_interval": 30
    }
  ]
}
```

### 3. Start Web Server
```bash
# Development
python3 sendfix_web_multi.py

# Production
./start_production.sh
```

### 4. Access Web Interface
Open browser to: `http://localhost:5001`

## Features

- **Multi-Session Support**: Connect to multiple FIX sessions simultaneously
- **QuickFIX Integration**: Professional-grade FIX engine with automatic sequence management
- **Real-Time Updates**: Live order status updates via WebSocket
- **Session Switching**: Easy switching between different FIX sessions in dropdown
- **Professional Interface**: Complete order management with all FIX fields
- **Order Operations**: Send, Replace, Cancel with proper FIX protocol handling
- **Message Logging**: Real-time FIX message display and logging
- **Session Recovery**: Automatic reconnection and sequence number management
- **Custom Tags**: Support for custom FIX tags and fields

## Usage

### Session Management
1. Select session from dropdown menu
2. Click "Connect" to establish FIX session
3. Monitor connection status in real-time
4. Switch between sessions without disconnecting others
5. Use "Show All Sessions" to view status of all sessions

### Order Management
1. Fill order form with required fields:
   - **Quantity**: Order size
   - **Symbol**: Trading symbol
   - **Side**: 1=Buy, 2=Sell, 5=Short Sell
   - **Order Type**: 1=Market, 2=Limit, 3=Stop, 4=Stop Limit
   - **Price**: For limit orders
2. Optional fields:
   - **Security ID Source** (Tag 22): ID source type
   - **Security ID** (Tag 48): Security identifier
   - **Sender Sub ID** (Tag 50): Trading desk identifier
   - **Client ID** (Tag 109): Client identifier
   - **Text** (Tag 58): Order comments
   - **Custom Tags**: Additional FIX tags (format: tag=value|tag=value)
3. Select appropriate session from dropdown
4. Click "Send Order" to submit
5. Monitor order status in Order Management table
6. Click on orders to populate form for replace/cancel operations

### Order Lifecycle
- **Sent**: Order submitted to counterparty
- **New**: Order accepted by counterparty
- **Partial Fill**: Order partially executed
- **Filled**: Order completely executed
- **Canceled**: Order canceled
- **Replaced**: Order modified
- **Rejected**: Order rejected by counterparty

## Architecture

See `WEBAPP_ARCHITECTURE.md` for detailed system architecture documentation.

## Production Deployment

See `DEPLOYMENT_GUIDE.md` for complete production setup instructions.

## Files

- `sendfix_web_multi.py` - Main Flask web application with WebSocket support
- `multi_fix_client.py` - Multi-session FIX client manager
- `quickfix_client.py` - QuickFIX/n client implementation with session recovery
- `templates/multi_session_index.html` - Professional web trading interface
- `multi_session_config.json` - Multi-session configurations
- `requirements.txt` - Python dependencies including QuickFIX
- `gunicorn_config.py` - Production WSGI server configuration
- `wsgi.py` - WSGI entry point for production deployment
- `start_production.sh` - Production startup script
- `sendfix-webapp.service` - Linux systemd service configuration

## Support

For technical support and documentation, refer to the architecture documentation and deployment guide.