# SendFix GUI Architecture

## Overview

SendFix is a professional FIX protocol client application with a comprehensive GUI interface built using Python and Tkinter. The system provides order management, session recovery, and bulk processing capabilities for financial trading operations.

## System Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GUI Layer     │    │  Business Logic │    │  Network Layer  │
│  (sendfix_gui)  │◄──►│  (fix_client)   │◄──►│  Socket/FIX     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   UI Controls   │    │ Session Manager │    │ FIX Server      │
│   Order Forms   │    │ Message Parser  │    │ (External)      │
│   Status Views  │    │ State Persist   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Module Structure

### 1. GUI Layer (`sendfix_gui.py`)

**Primary Class:** `FixClientGUI`

**Responsibilities:**
- User interface management
- Order form handling
- Real-time status display
- Message logging
- Thread communication

**Key Components:**
- **Connection Management**: Status indicators, connect/disconnect controls
- **Order Composer**: Professional order entry form with validation
- **Order Management**: Real-time order tracking with color-coded status
- **Message Display**: Scrollable log for FIX message monitoring

### 2. Business Logic (`fix_client.py`)

**Primary Class:** `FixClient`

**Responsibilities:**
- FIX protocol implementation
- Session state management
- Message construction/parsing
- Sequence number handling
- Error recovery

**Key Features:**
- Session persistence via JSON state files
- Automatic reconnection and recovery
- Message resend handling
- Bulk order processing

## Data Flow Architecture

### Message Flow

```
User Input → GUI Form → FixClient → FIX Message → Network → FIX Server
                                        ↓
Session State ← JSON File ← State Manager ← Message Parser ← Response
                                        ↓
GUI Update ← Message Queue ← Callback ← Execution Report ← FIX Server
```

### Threading Model

```
Main Thread (GUI)
├── UI Event Handling
├── Form Processing
└── Message Queue Monitoring (100ms intervals)

Background Thread (Network)
├── Socket Communication
├── Message Reception
└── Callback Execution
```

## Component Details

### GUI Architecture

#### Tab Structure
- **Basic Commands**: Raw FIX messaging, sequence control
- **Order Composer**: Professional order entry and management

#### Order Management System
```
Order Form → Validation → FIX Message → Send → Store → Display
     ↓                                                    ↑
Form Fields                                        Order Tree View
├── Quantity                                       ├── Status Colors
├── Price                                          ├── Selection Events
├── Side/Type                                      └── Management Actions
├── Security Details
└── Custom Tags
```

#### Status Management
- **Connection Status**: Visual indicators (red/green)
- **Order Status**: Color-coded tree view with real-time updates
- **Message Logging**: Comprehensive FIX message history

### FIX Client Architecture

#### Session Management
```
Configuration → Connection → Logon → Active Session
     ↓              ↓          ↓           ↓
Config File    Socket Setup  Sequence   Message Flow
sendfix.cfg    Host:Port     Numbers    Send/Receive
```

#### Message Processing Pipeline
```
Raw Input → Parse → Validate → Construct → Send → Store
                                    ↓
Incoming ← Parse ← Receive ← Network ← Response
    ↓
Process → Update State → Callback → GUI Update
```

## Configuration System

### Configuration File (`sendfix.cfg`)
```ini
[DEFAULT]
ServerIP=hk1pvstaslp01
Port=5655
FixVersion=FIX.4.2
SenderCompId=ASIATEST5
TargetCompId=LQNT
HeartbeatInterval=30
```

### Session State (`session_state.json`)
```json
{
  "outgoing_seq": 1222,
  "incoming_seq": 507,
  "sender_comp_id": "ASIATEST5",
  "target_comp_id": "LQNT"
}
```

## Key Design Patterns

### 1. Observer Pattern
- GUI registers callbacks with FIX client
- Execution reports trigger GUI updates
- Message queue enables thread-safe communication

### 2. State Pattern
- Session state persistence across restarts
- Order status lifecycle management
- Connection state tracking

### 3. Command Pattern
- User actions translated to FIX messages
- Standardized message construction
- Undo/redo capability through message storage

## Security & Error Handling

### Session Recovery
- Automatic sequence number persistence
- Gap detection and resend requests
- Connection retry mechanisms
- Message storage for replay

### Error Handling
- Input validation at GUI level
- Network error recovery
- Invalid message protection
- Comprehensive logging

## Performance Considerations

### Threading Strategy
- Non-blocking GUI operations
- Background network processing
- Message queue buffering
- Periodic GUI updates (100ms)

### Memory Management
- Limited message history storage
- Efficient order data structures
- Automatic cleanup of old sessions

## Extension Points

### Custom Message Types
- Pluggable message handlers
- Custom tag support
- Flexible message construction

### GUI Customization
- Modular tab system
- Configurable order fields
- Extensible status displays

## Dependencies

### Core Libraries
- `tkinter`: GUI framework
- `simplefix`: FIX protocol implementation
- `threading`: Concurrent processing
- `queue`: Thread-safe communication
- `socket`: Network communication

### Standard Libraries
- `configparser`: Configuration management
- `json`: State persistence
- `logging`: Comprehensive logging
- `datetime`: Timestamp handling

## Deployment Architecture

### Standalone Application
```
SendFix GUI Application
├── Python Runtime
├── Required Libraries
├── Configuration Files
└── Session State Files
```

### File Structure
```
WSL_Project/
├── sendfix_gui.py      # Main GUI application
├── fix_client.py       # FIX protocol client
├── sendfix.cfg         # Configuration
├── session_state.json  # Session persistence
├── fix_orders.txt      # Bulk order input
└── sendfix.log         # Application logs
```

## Scalability Considerations

### Multi-Session Support
- Session-specific state files
- Configurable connection parameters
- Independent message flows

### Performance Optimization
- Efficient message parsing
- Minimal GUI updates
- Optimized network I/O

## Monitoring & Debugging

### Logging System
- Comprehensive message logging
- Error tracking and reporting
- Performance metrics
- Session event recording

### Debug Features
- Raw message display
- Sequence number monitoring
- Connection status tracking
- Order lifecycle visibility