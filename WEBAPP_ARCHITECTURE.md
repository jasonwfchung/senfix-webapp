# SendFix Multi-Session Web Application Architecture

## Overview
A professional web-based FIX protocol trading client supporting multiple concurrent sessions with QuickFIX/n engine, real-time order management, and execution report processing.

## Architecture Layers

### 1. Presentation Layer (Web Frontend)
- **Technology**: HTML5, CSS3, JavaScript, Socket.IO Client
- **File**: `templates/multi_session_index.html`
- **Features**:
  - Responsive professional trading interface
  - Real-time WebSocket communication
  - Multi-session dropdown with live status
  - Complete order composer with FIX field validation
  - Live order management table with click-to-edit
  - Real-time message log with FIX protocol display
  - Order lifecycle tracking (Sent → New → Filled/Canceled)

### 2. Application Layer (Web Backend)
- **Technology**: Flask, Flask-SocketIO, Gunicorn
- **File**: `sendfix_web_multi.py`
- **Components**:
  - REST API endpoints for order operations
  - WebSocket handlers for real-time updates
  - Multi-session management controller
  - Order lifecycle management with execution report processing
  - Message broadcasting to all connected clients
  - Session-specific order routing

### 3. Business Logic Layer (Multi-Session Manager)
- **Technology**: Python
- **File**: `multi_fix_client.py`
- **Features**:
  - Concurrent session management (multiple FIX connections)
  - Dynamic session configuration loading from JSON
  - Real-time connection state tracking
  - Session switching without disconnecting others
  - Client instance lifecycle management
  - Active session routing for order operations

### 4. Protocol Layer (QuickFIX Client)
- **Technology**: QuickFIX/n Python, FIX 4.2 Protocol
- **File**: `quickfix_client.py`
- **Features**:
  - Professional FIX protocol implementation
  - Automatic session persistence and recovery
  - Message construction with proper FIX formatting
  - Tag 60 (TransactTime) automatic insertion
  - Sequence number management and resend handling
  - Connection state management (running, logged_on flags)
  - Execution report parsing and callback handling

### 5. Configuration Layer
- **Files**: 
  - `multi_session_config.json` - Multi-session definitions
  - `sendfix.cfg` - Legacy FIX client configuration
  - `quickfix_client.cfg` - Auto-generated QuickFIX configuration
- **Purpose**: Environment-specific settings and session parameters

## Component Interaction Flow

```
Web Browser (Multiple Users)
    ↓ HTTP/WebSocket
Flask Web Server (sendfix_web_multi.py)
    ↓ Python API
Multi-Session Manager (multi_fix_client.py)
    ↓ Session Management
QuickFIX Client Pool (quickfix_client.py)
    ↓ FIX Protocol (Multiple Connections)
Trading Servers (Multiple Counterparties)
```

## Key Features

### Multi-Session Support
- **Concurrent Connections**: Multiple FIX sessions simultaneously active
- **Session Isolation**: Independent connection management per session
- **Dynamic Switching**: Real-time session selection from dropdown
- **Status Tracking**: Live connection status for all sessions
- **Session Persistence**: Maintains connections when switching between sessions

### Real-Time Order Management
- **Complete Order Lifecycle**: Send → New → Partial Fill → Filled/Canceled/Replaced
- **Live Updates**: WebSocket-based real-time status updates to all clients
- **Field Synchronization**: Server execution reports update all order fields
- **Replace/Cancel**: Proper OrigClOrdID handling for order modifications
- **Click-to-Edit**: Click orders in table to populate form for modifications

### Professional Trading Features
- **FIX Protocol Compliance**: Full FIX 4.2 implementation with QuickFIX/n
- **Comprehensive Tag Support**: All standard FIX tags plus custom tag support
- **Execution Reports**: Real-time processing of server responses (35=8)
- **Session Recovery**: Automatic reconnection and sequence management
- **Message Logging**: Complete FIX message history with timestamps
- **Order Validation**: Client-side and server-side field validation

## Data Flow

### Order Submission Flow
1. **Web Form** → User fills order details and selects session
2. **Frontend Validation** → Required field validation (Qty, Symbol)
3. **REST API** → POST to `/api/send_order` with session_name
4. **Session Routing** → Multi-client routes to specified session
5. **QuickFIX** → Constructs proper FIX message with ClOrdID generation
6. **Network** → Sends NewOrderSingle (35=D) to trading server
7. **WebSocket Broadcast** → Notifies all clients of order submission
8. **Order Tracking** → Adds order to management table

### Execution Report Flow
1. **Trading Server** → Sends execution report (35=8)
2. **QuickFIX Callback** → `fromApp()` receives and parses message
3. **Message Handler** → Processes execution report fields
4. **Order Update** → Updates order status, OrderID, and execution details
5. **WebSocket Broadcast** → Real-time updates to all connected clients
6. **UI Refresh** → Order management table updates automatically

### Session Management Flow
1. **Session Selection** → User selects session from dropdown
2. **Connection Request** → POST to `/api/connect` with session_name
3. **QuickFIX Initialization** → Creates session-specific configuration
4. **Connection Establishment** → Initiates FIX logon sequence
5. **Status Updates** → Real-time connection status via WebSocket
6. **Session Tracking** → Maintains session in multi-client pool

## Session Management

### Session Configuration
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

### Connection States
- **Not Connected**: No active connection
- **Connecting**: Connection attempt in progress
- **Connected**: Active FIX session established and logged on
- **Disconnected**: Session terminated by counterparty or error

## API Endpoints

### Session Management
- `GET /api/sessions` - List all sessions with real-time connection status
- `POST /api/connect` - Connect to specified session
- `POST /api/disconnect` - Disconnect from specified session
- `GET /api/can_send_orders` - Check if orders can be sent (debug endpoint)

### Order Operations
- `POST /api/send_order` - Submit new order to specified session
- `POST /api/replace_order` - Replace existing order (35=G)
- `POST /api/cancel_order` - Cancel existing order (35=F)
- `GET /api/orders` - Retrieve all orders across all sessions

### WebSocket Events
- `order_updated` - Real-time order status updates with complete order data
- `log_message` - FIX message logging with timestamps
- `connection_result` - Session connection status updates
- `connected` - Client connection acknowledgment

## Security Considerations

### Network Security
- **CORS Configuration**: Controlled cross-origin access
- **Session Isolation**: Separate FIX sessions per trading environment
- **Connection Timeout**: Prevents hanging connections
- **Input Validation**: Comprehensive field validation

### Data Integrity
- **Field Validation**: Client-side and server-side validation
- **Sequence Management**: QuickFIX automatic sequence number handling
- **Error Handling**: Comprehensive error reporting and recovery
- **Message Persistence**: QuickFIX file-based message storage

## Scalability Features

### Multi-User Support
- **Concurrent Access**: Multiple traders can use simultaneously
- **Shared Order Book**: All users see real-time order updates
- **WebSocket Broadcasting**: Efficient real-time communication
- **Session Sharing**: Multiple users can monitor same sessions

### Performance Optimization
- **Non-Blocking Connections**: Threaded connection handling
- **Efficient Parsing**: Optimized FIX message processing
- **Memory Management**: Proper resource cleanup
- **Connection Pooling**: Reuse of established sessions

## Production Deployment

### Development Environment
```
WSL/Linux Environment
├── Python Virtual Environment
├── QuickFIX Library
├── Flask Web Server (Port 5001)
├── Gunicorn WSGI Server
└── WebSocket Communication
```

### Production Architecture
```
Load Balancer (nginx)
    ↓
Gunicorn WSGI Server
    ↓
Flask Application
    ↓
QuickFIX Session Pool
    ↓
Multiple FIX Connections
```

### Production Features
- **Gunicorn WSGI**: Production-grade web server
- **Gevent Workers**: Async WebSocket support
- **Service Management**: systemd service configuration
- **Log Management**: Separate access and error logs
- **Process Management**: Automatic restart and monitoring

## Technology Stack

### Backend
- **Python 3.12+**
- **Flask 2.3+** - Web framework
- **Flask-SocketIO 5.3+** - WebSocket support
- **QuickFIX 1.15+** - Professional FIX protocol implementation
- **Gunicorn 21.2+** - Production WSGI server
- **Gevent** - Async worker support

### Frontend
- **HTML5** - Modern web standards
- **CSS3** - Professional trading interface design
- **JavaScript ES6+** - Client-side logic and real-time updates
- **Socket.IO 4.0+** - Real-time bidirectional communication

### Infrastructure
- **WSL/Linux** - Development and production environment
- **Virtual Environment** - Python dependency isolation
- **Git** - Version control and deployment
- **systemd** - Service management

## File Structure
```
webapp/
├── sendfix_web_multi.py          # Main Flask web application
├── multi_fix_client.py           # Multi-session manager
├── quickfix_client.py            # QuickFIX implementation
├── multi_session_config.json     # Session configurations
├── sendfix.cfg                   # Legacy FIX configuration
├── templates/
│   └── multi_session_index.html  # Professional web interface
├── requirements.txt               # Python dependencies
├── gunicorn_config.py            # Production server config
├── wsgi.py                       # WSGI entry point
├── start_production.sh           # Production startup script
├── sendfix-webapp.service        # systemd service
├── store/                        # QuickFIX session storage
├── log/                          # QuickFIX message logs
└── logs/                         # Web application logs
```

## Troubleshooting

### Common Issues
- **Connection Timeout**: Check network connectivity and FIX server availability
- **Sequence Errors**: QuickFIX handles automatically with resend requests
- **Memory Leaks**: SWIG warnings are normal for QuickFIX usage
- **Session Status**: Use `/api/can_send_orders` for debugging connection state

### Debug Features
- **Console Logging**: Comprehensive debug output in development mode
- **Browser Console**: Frontend debug messages for troubleshooting
- **FIX Message Logs**: Complete message history in log files
- **Real-time Status**: Live connection status in web interface

## Future Enhancements

### Planned Features
- **User Authentication**: Individual trader login system
- **Order History**: Persistent order storage with database
- **Advanced Analytics**: Trading performance metrics and reporting
- **Mobile Support**: Responsive mobile trading interface
- **Risk Management**: Pre-trade risk checks and limits

### Scalability Improvements
- **Database Integration**: PostgreSQL for order and session storage
- **Redis Caching**: Session state and order caching
- **Microservices**: Service-oriented architecture
- **Container Deployment**: Docker containerization
- **High Availability**: Multi-instance deployment with load balancing