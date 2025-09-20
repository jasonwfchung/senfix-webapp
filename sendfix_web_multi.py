#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import json
import threading
import time
from datetime import datetime
from multi_fix_client import MultiFixClient
import quickfix as fix
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sendfix_multi_secret_key_change_in_production'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Load users from file
def load_users():
    try:
        with open('users.json', 'r') as f:
            return json.load(f)['users']
    except:
        return {'admin': {'password': 'admin123', 'role': 'administrator'}}

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# API authentication decorator
def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Global variables
multi_client = None
user_orders = {}  # Track orders per user: {username: [orders]}
connected_clients = []
users = load_users()
session_states = {}  # Track session connection states
user_sessions = {}  # Track each user's selected FIX session

class WebMessageHandler:
    def __init__(self, socketio):
        self.socketio = socketio
        
    def log_message(self, message):
        """Send log message to all connected clients"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.socketio.emit('log_message', {'message': log_entry})
        
        # Process execution reports for order status updates
        if "ExecutionReport" in message or "35=8" in message:
            self.process_execution_report(message)
        elif "OrderCancelReject" in message or "35=9" in message:
            self.process_cancel_reject(message)
            
    def process_execution_report(self, message):
        """Process execution report and update order status"""
        try:
            print(f"\n=== Processing Execution Report ===")
            print(f"Raw message: {message}")
            
            # Parse message fields - handle different separators
            fields = {}
            
            # Try different separators
            if '\x01' in message:
                pairs = message.split('\x01')
            elif '|' in message:
                pairs = message.split('|')
            else:
                pairs = message.split()
                
            print(f"Split into pairs: {pairs[:10]}...")  # Show first 10 pairs
                
            for pair in pairs:
                if '=' in pair and pair.strip():
                    try:
                        tag, value = pair.split('=', 1)
                        fields[tag.strip()] = value.strip()
                    except:
                        continue
                        
            print(f"Parsed fields: {dict(list(fields.items())[:10])}...")  # Show first 10 fields
                    
            clordid = fields.get('11', '')
            orig_clordid = fields.get('41', '')
            order_id = fields.get('37', '')
            exec_type = fields.get('150', fields.get('39', ''))
            
            # Extract additional fields from execution report
            symbol = fields.get('55', '')
            side = fields.get('54', '')
            qty = fields.get('38', fields.get('14', ''))  # OrderQty or CumQty
            price = fields.get('44', fields.get('31', ''))  # Price or LastPx
            
            print(f"Key fields - ClOrdID: {clordid}, OrigClOrdID: {orig_clordid}, OrderID: {order_id}, ExecType: {exec_type}")
            print(f"Additional fields - Symbol: {symbol}, Side: {side}, Qty: {qty}, Price: {price}")
            
            # Status mapping
            status_map = {
                '0': 'New', '1': 'Partial Fill', '2': 'Filled',
                '4': 'Canceled', '5': 'Replaced', '6': 'Pending Cancel',
                '8': 'Rejected', 'A': 'Pending New', 'E': 'Pending Replace'
            }
            
            new_status = status_map.get(exec_type, f'Status({exec_type})')
            print(f"New status: {new_status}")
            
            # Update order status for all users
            updated = False
            for username, user_order_list in user_orders.items():
                for order in user_order_list:
                    if order['ClOrdID'] == clordid or (orig_clordid and order['ClOrdID'] == orig_clordid):
                        old_status = order['Status']
                        order['Status'] = new_status
                        
                        # Update OrderID if provided
                        if order_id:
                            order['OrderID'] = order_id
                            
                        # Update other fields if provided in execution report
                        if symbol:
                            order['Symbol'] = symbol
                        if side:
                            order['Side'] = side
                        if qty:
                            order['Qty'] = qty
                        if price:
                            order['Price'] = price
                            
                        # For replace orders, update ClOrdID to new one
                        if orig_clordid and order['ClOrdID'] == orig_clordid and clordid:
                            order['ClOrdID'] = clordid
                            
                        print(f"*** ORDER UPDATED: {old_status} -> {new_status} ***")
                        print(f"Updated fields: OrderID={order.get('OrderID', 'N/A')}, Symbol={order.get('Symbol', 'N/A')}, Qty={order.get('Qty', 'N/A')}, Price={order.get('Price', 'N/A')}")
                        
                        # Emit order update to specific user only
                        self.socketio.emit('order_updated', {'order': order, 'all_orders': user_order_list}, room=f'user_{username}')
                        self.log_message(f"Updated order {clordid}: {old_status} -> {new_status}, OrderID={order_id}, Qty={qty}, Price={price}")
                        updated = True
                        break
                if updated:
                    break
                    
            if not updated:
                self.log_message(f"Order ClOrdID:{clordid} or OrigClOrdID:{orig_clordid} not found for status update")
                    
        except Exception as e:
            self.log_message(f"Error processing execution report: {e}")
            
    def process_cancel_reject(self, message):
        """Process order cancel reject"""
        try:
            fields = {}
            for pair in message.split('|'):
                if '=' in pair:
                    tag, value = pair.split('=', 1)
                    fields[tag.strip()] = value.strip()
                    
            orig_clordid = fields.get('41', '')
            
            for username, user_order_list in user_orders.items():
                for order in user_order_list:
                    if order['ClOrdID'] == orig_clordid:
                        order['Status'] = 'Cancel Rejected'
                        self.socketio.emit('order_updated', {'order': order, 'all_orders': user_order_list}, room=f'user_{username}')
                        break
                    
        except Exception as e:
            self.log_message(f"Error processing cancel reject: {e}")

# Session state callback
def session_state_callback(state, session_id):
    """Handle session state changes"""
    global session_states
    session_states[session_id] = state
    
    # Log detailed state change
    message_handler.log_message(f"*** WEBAPP: session_state_callback() called - {session_id} -> {state} ***")
    message_handler.log_message(f"*** WEBAPP: Emitting 'session_state_changed' via WebSocket ***")
    
    print(f"*** CONSOLE: Session state changed: {session_id} -> {state} ***")
    print(f"*** CONSOLE: Emitting WebSocket event ***")
    
    socketio.emit('session_state_changed', {
        'session_id': session_id,
        'state': state
    })
    
    print(f"*** CONSOLE: WebSocket event emitted ***")

# Initialize message handler
message_handler = WebMessageHandler(socketio)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and users[username]['password'] == password:
            session['user'] = username
            session['role'] = users[username]['role']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('multi_session_index.html', user=session['user'], role=session['role'])

@app.route('/api/sessions')
@api_login_required
def get_sessions():
    """Get available sessions with real-time status"""
    global multi_client
    if not multi_client:
        multi_client = MultiFixClient(message_callback=message_handler.log_message, session_callback=session_state_callback)
    
    sessions = []
    for session_name in multi_client.get_session_names():
        # Check real-time connection status
        connected = False
        
        # Debug: Show what sessions are actually in the dict
        message_handler.log_message(f"DEBUG: Available sessions in dict: {list(multi_client.sessions.keys())}")
        message_handler.log_message(f"DEBUG: Looking for session: {session_name}")
        
        if session_name in multi_client.sessions:
            client = multi_client.sessions[session_name]
            # Use QuickFIX's real-time connection check
            if client.session_id:
                try:
                    connected = client.is_connected()
                    message_handler.log_message(f"DEBUG: Session {session_name} connection check: {connected} (session_id: {client.session_id}, running: {client.running}, logged_on: {client.logged_on})")
                except Exception as e:
                    connected = False
                    message_handler.log_message(f"DEBUG: Session {session_name} connection check failed: {e}")
            else:
                message_handler.log_message(f"DEBUG: Session {session_name} has no session_id")
        else:
            message_handler.log_message(f"DEBUG: Session {session_name} not in sessions dict")
        
        # Always generate session_id from config
        session_id = None
        if hasattr(multi_client, 'session_configs'):
            for config in multi_client.session_configs:
                if config['name'] == session_name:
                    session_id = f"{config['fix_version']}:{config['sender_comp_id']}->{config['target_comp_id']}"
                    break
        
        sessions.append({
            'name': session_name,
            'session_id': session_id,
            'connected': connected
        })
        
        message_handler.log_message(f"DEBUG: Final session status - {session_name}: {connected}")
        
        # Double-check connection status for sessions that have clients
        if session_name in multi_client.sessions:
            client = multi_client.sessions[session_name]
            if client.logged_on and client.running:
                connected = True
                message_handler.log_message(f"DEBUG: Session {session_name} is actually connected (logged_on: {client.logged_on}, running: {client.running})")
            else:
                message_handler.log_message(f"DEBUG: Session {session_name} client exists but not fully connected (logged_on: {client.logged_on}, running: {client.running})")
    
    message_handler.log_message(f"DEBUG: Active session: {multi_client.active_session}")
    message_handler.log_message(f"DEBUG: All session clients: {[(name, client.logged_on if hasattr(client, 'logged_on') else 'N/A', client.running if hasattr(client, 'running') else 'N/A') for name, client in multi_client.sessions.items()]}")
    message_handler.log_message(f"DEBUG: Returning sessions data: {sessions}")
    return jsonify({'sessions': sessions})

@app.route('/api/connect', methods=['POST'])
@api_login_required
def connect_session():
    """Connect to a session"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    
    if not multi_client:
        multi_client = MultiFixClient(message_callback=message_handler.log_message, session_callback=session_state_callback)
    
    def connect_thread():
        success, message = multi_client.connect_session(session_name)
        
        # CRITICAL: ALWAYS refresh user session mapping on connection attempt
        # This ensures we use the fresh client object, not stale ones
        current_user = session.get('user')
        if current_user:
            # Force clear any existing mapping
            if current_user in user_sessions:
                old_mapping = user_sessions[current_user]
                del user_sessions[current_user]
                message_handler.log_message(f"*** CLEARED OLD USER SESSION: {current_user} -> {old_mapping} ***")
            
            # Set fresh mapping to new session (even if connection fails, clear old mapping)
            if success:
                user_sessions[current_user] = session_name
                message_handler.log_message(f"*** SET FRESH USER SESSION: {current_user} -> {session_name} ***")
            
            message_handler.log_message(f"*** USER_SESSIONS AFTER REFRESH: {user_sessions} ***")
        
        socketio.emit('connection_result', {
            'success': success,
            'message': message,
            'session_name': session_name,
            'force_dropdown_refresh': True,
            'clear_user_mapping': True  # Signal frontend to clear any cached mappings
        })
    
    threading.Thread(target=connect_thread, daemon=True).start()
    return jsonify({'status': 'connecting'})

@app.route('/api/disconnect', methods=['POST'])
@api_login_required
def disconnect_session():
    """Disconnect from a session"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    
    if multi_client:
        multi_client.disconnect_session(session_name)
        
    return jsonify({'status': 'disconnected'})

@app.route('/api/set_user_session', methods=['POST'])
@api_login_required
def set_user_session():
    """Set user's selected FIX session"""
    data = request.json
    session_name = data.get('session_name')
    
    if not session_name:
        return jsonify({'success': False, 'message': 'No session name provided'})
    
    user_sessions[session['user']] = session_name
    message_handler.log_message(f"User {session['user']} selected session: {session_name}")
    
    return jsonify({'success': True, 'message': f'Session set to {session_name}'})

@app.route('/api/get_user_session')
@api_login_required
def get_user_session():
    """Get user's currently selected FIX session"""
    user_session = user_sessions.get(session['user'])
    return jsonify({'session_name': user_session})

@app.route('/api/send_order', methods=['POST'])
@api_login_required
def send_order():
    """Send new order"""
    global multi_client, user_orders
    
    if not multi_client:
        print("DEBUG: No multi_client")
        return jsonify({'success': False, 'message': 'No multi-client initialized'})
    
    # Get user's selected session
    user_session = user_sessions.get(session['user'])
    print(f"DEBUG: User {session['user']} user_sessions lookup: {user_session}")
    print(f"DEBUG: Available user_sessions: {user_sessions}")
    message_handler.log_message(f"*** SEND ORDER DEBUG: User {session['user']} -> {user_session} ***")
    message_handler.log_message(f"*** USER_SESSIONS STATE: {user_sessions} ***")
    
    if not user_session:
        return jsonify({'success': False, 'message': 'No session selected. Please select a session first.'})
    
    print(f"DEBUG: User {session['user']} selected session: {user_session}")
    print(f"DEBUG: Available multi_client sessions: {list(multi_client.sessions.keys())}")
    message_handler.log_message(f"*** AVAILABLE SESSIONS: {list(multi_client.sessions.keys())} ***")
    
    # Check if user's session is available and connected
    if user_session not in multi_client.sessions:
        print(f"DEBUG: Session {user_session} not found in multi_client.sessions")
        message_handler.log_message(f"*** ERROR: Session {user_session} not found in sessions dict ***")
        return jsonify({'success': False, 'message': f'Session {user_session} not available'})
    
    client = multi_client.sessions[user_session]
    print(f"DEBUG: Client found - session_id: {client.session_id}, running: {client.running}")
    message_handler.log_message(f"*** CLIENT STATUS: session_id={client.session_id}, running={client.running}, logged_on={client.logged_on} ***")
    message_handler.log_message(f"*** CLIENT OBJECT ID: {id(client)} ***")
    message_handler.log_message(f"*** SESSION_ID OBJECT ID: {id(client.session_id) if client.session_id else 'None'} ***")
    
    # CRITICAL: Force user session mapping refresh to ensure fresh client reference
    user_sessions[session['user']] = user_session
    message_handler.log_message(f"*** FORCED USER SESSION REFRESH: {session['user']} -> {user_session} ***")
    
    # Use is_connected() method which trusts our internal state
    if not client.is_connected():
        print(f"DEBUG: Session {user_session} validation failed - is_connected returned False")
        message_handler.log_message(f"*** VALIDATION FAILED: is_connected()=False (logged_on={client.logged_on}, running={client.running}) ***")
        return jsonify({'success': False, 'message': f'Session {user_session} is not connected'})
    
    # Set user's session as active for this operation
    multi_client.active_session = user_session
    print(f"DEBUG: Set active session to user's selection: {user_session}")
    
    try:
        data = request.json
        session_name = data.get('session_name')
        
        # Use the specified session if provided
        if session_name and session_name in multi_client.sessions:
            client = multi_client.sessions[session_name]
            if not (client.session_id and client.running):
                return jsonify({'success': False, 'message': f'Session {session_name} is not connected'})
            multi_client.active_session = session_name
        
        # Build custom tags
        tag_parts = []
        if data.get('idsource') and data.get('secid'):
            tag_parts.append(f"22={data['idsource']}")
            tag_parts.append(f"48={data['secid']}")
        if data.get('sendersubid'):
            tag_parts.append(f"50={data['sendersubid']}")
        if data.get('onbehalfofsubid'):
            tag_parts.append(f"115={data['onbehalfofsubid']}")
        if data.get('clientid'):
            tag_parts.append(f"109={data['clientid']}")
        if data.get('text'):
            tag_parts.append(f"58={data['text']}")
        if data.get('custom_tags'):
            tag_parts.append(data['custom_tags'])
        
        custom_tags = "|".join(tag_parts) if tag_parts else None
        
        client = multi_client.get_current_client()
        print(f"DEBUG: Using client for session: {multi_client.active_session}")
        print(f"DEBUG: Client session_id: {client.session_id if client else 'None'}")
        message_handler.log_message(f"*** SEND ORDER CLIENT OBJECT ID: {id(client) if client else 'None'} ***")
        message_handler.log_message(f"*** SEND ORDER SESSION_ID OBJECT ID: {id(client.session_id) if client and client.session_id else 'None'} ***")
        
        # Verify this is the same client object we checked earlier
        original_client = multi_client.sessions[user_session]
        if client != original_client:
            message_handler.log_message(f"*** WARNING: CLIENT OBJECT MISMATCH! Original: {id(original_client)}, Current: {id(client)} ***")
        else:
            message_handler.log_message(f"*** CLIENT OBJECT MATCH CONFIRMED ***")
        
        # Final verification before sending
        message_handler.log_message(f"*** FINAL PRE-SEND CHECK: Client={id(client)}, SessionID={client.session_id}, LoggedOn={client.logged_on} ***")
        
        success, actual_clordid = client.send_new_order_single(
            symbol=data['symbol'],
            side=data['side'],
            quantity=data['qty'],
            price=data.get('price') if data.get('price') else None,
            order_type=data['order_type'],
            tif=data['tif'],
            custom_tags=custom_tags
        )
        
        message_handler.log_message(f"*** ORDER SEND RESULT: success={success}, clordid={actual_clordid} ***")
        
        if success and actual_clordid:
            # Get FIX session ID from active session
            session_id = None
            for config in multi_client.session_configs:
                if config['name'] == multi_client.active_session:
                    session_id = f"{config['fix_version']}:{config['sender_comp_id']}->{config['target_comp_id']}"
                    break
            
            new_order = {
                'ClOrdID': actual_clordid,
                'OrderID': '',
                'Symbol': data['symbol'],
                'Side': data['side'],
                'Qty': data['qty'],
                'Price': data.get('price', ''),
                'Status': 'Sent',
                'Session': session_id or multi_client.active_session,
                'IDSource': data.get('idsource', ''),
                'SecurityID': data.get('secid', ''),
                'SenderSubID': data.get('sendersubid', ''),
                'OnBehalfOfSubID': data.get('onbehalfofsubid', ''),
                'ClientID': data.get('clientid', ''),
                'Text': data.get('text', ''),
                'CustomTags': data.get('custom_tags', ''),
                'TimeInForce': data.get('tif', '0')
            }
            # Initialize user orders if not exists
            username = session['user']
            if username not in user_orders:
                user_orders[username] = []
            
            user_orders[username].append(new_order)
            
            # Emit new order only to the user who created it
            socketio.emit('order_updated', {'order': new_order, 'all_orders': user_orders[username]}, room=f'user_{username}')
            
            return jsonify({'success': True, 'clordid': actual_clordid})
        else:
            return jsonify({'success': False, 'message': 'Failed to send order'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/replace_order', methods=['POST'])
@api_login_required
def replace_order():
    """Replace existing order"""
    global multi_client
    
    if not multi_client or not multi_client.sessions:
        return jsonify({'success': False, 'message': 'No sessions available'})
    
    # Get user's selected session
    user_session = user_sessions.get(session['user'])
    if not user_session:
        return jsonify({'success': False, 'message': 'No session selected. Please select a session first.'})
    
    if user_session not in multi_client.sessions:
        return jsonify({'success': False, 'message': f'Session {user_session} not available'})
    
    client = multi_client.sessions[user_session]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': f'Session {user_session} is not connected'})
    
    multi_client.active_session = user_session
    
    try:
        data = request.json
        client = multi_client.get_current_client()
        
        success = client.send_order_cancel_replace_request(
            orig_clordid=data['orig_clordid'],
            symbol=data['symbol'],
            side=data['side'],
            quantity=data['qty'],
            price=data.get('price') if data.get('price') else None,
            order_type=data['order_type'],
            tif=data['tif']
        )
        
        if success:
            # Update order status for current user only
            username = session['user']
            user_order_list = user_orders.get(username, [])
            for order in user_order_list:
                if order['ClOrdID'] == data['orig_clordid']:
                    order['Status'] = 'Replace Sent'
                    socketio.emit('order_updated', {'order': order, 'all_orders': user_order_list}, room=f'user_{username}')
                    break
                    
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Failed to send replace'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/cancel_order', methods=['POST'])
@api_login_required
def cancel_order():
    """Cancel existing order"""
    global multi_client
    
    if not multi_client or not multi_client.sessions:
        return jsonify({'success': False, 'message': 'No sessions available'})
    
    # Get user's selected session
    user_session = user_sessions.get(session['user'])
    if not user_session:
        return jsonify({'success': False, 'message': 'No session selected. Please select a session first.'})
    
    if user_session not in multi_client.sessions:
        return jsonify({'success': False, 'message': f'Session {user_session} not available'})
    
    client = multi_client.sessions[user_session]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': f'Session {user_session} is not connected'})
    
    multi_client.active_session = user_session
    
    try:
        data = request.json
        client = multi_client.get_current_client()
        
        success = client.send_order_cancel_request(
            orig_clordid=data['clordid'],
            symbol=data['symbol'],
            side=data['side'],
            quantity=data['qty']
        )
        
        if success:
            # Update order status for current user only
            username = session['user']
            user_order_list = user_orders.get(username, [])
            for order in user_order_list:
                if order['ClOrdID'] == data['clordid']:
                    order['Status'] = 'Cancel Sent'
                    socketio.emit('order_updated', {'order': order, 'all_orders': user_order_list}, room=f'user_{username}')
                    break
                    
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Failed to send cancel'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/orders')
@api_login_required
def get_orders():
    """Get current user's orders only"""
    username = session['user']
    user_order_list = user_orders.get(username, [])
    return jsonify({'orders': user_order_list})

@app.route('/api/send_raw_fix', methods=['POST'])
@api_login_required
def send_raw_fix():
    """Send raw FIX message"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    raw_fix = data.get('raw_fix')
    
    if not multi_client or session_name not in multi_client.sessions:
        return jsonify({'success': False, 'message': 'Session not available'})
    
    client = multi_client.sessions[session_name]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': 'Session not connected'})
    
    try:
        # Update Tag 60 (TransactTime) before sending
        from datetime import datetime
        current_time = datetime.utcnow().strftime('%Y%m%d-%H:%M:%S.%f')[:-3]
        
        # Parse existing tags and update/add Tag 60
        tags = {}
        for pair in raw_fix.split('|'):
            if '=' in pair:
                tag, value = pair.split('=', 1)
                tags[tag.strip()] = value.strip()
        
        # Update Tag 60
        tags['60'] = current_time
        
        # Rebuild raw_fix string
        updated_raw_fix = '|'.join([f"{tag}={value}" for tag, value in tags.items()])
        
        success = client.send_raw_fix(updated_raw_fix)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/send_custom_message', methods=['POST'])
@api_login_required
def send_custom_message():
    """Send custom message"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    custom_message = data.get('custom_message')
    
    if not multi_client or session_name not in multi_client.sessions:
        return jsonify({'success': False, 'message': 'Session not available'})
    
    client = multi_client.sessions[session_name]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': 'Session not connected'})
    
    try:
        success = client.send_custom_message(custom_message)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/send_bulk_orders', methods=['POST'])
@api_login_required
def send_bulk_orders():
    """Send bulk orders from text data"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    bulk_data = data.get('bulk_data')
    
    if not multi_client or session_name not in multi_client.sessions:
        return jsonify({'success': False, 'message': 'Session not available'})
    
    client = multi_client.sessions[session_name]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': 'Session not connected'})
    
    try:
        # Write bulk data to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(bulk_data)
            temp_filename = f.name
        
        # Send orders from file
        client.send_orders_from_file(temp_filename)
        
        # Count orders (lines - 1 for header)
        order_count = len(bulk_data.strip().split('\n')) - 1
        
        # Clean up temp file
        import os
        os.unlink(temp_filename)
        
        return jsonify({'success': True, 'count': order_count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/send_heartbeat', methods=['POST'])
@api_login_required
def send_heartbeat():
    """Send heartbeat message"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    
    if not multi_client or session_name not in multi_client.sessions:
        return jsonify({'success': False, 'message': 'Session not available'})
    
    client = multi_client.sessions[session_name]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': 'Session not connected'})
    
    try:
        success = client.send_custom_message('35=0')  # Heartbeat
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/send_test_request', methods=['POST'])
@api_login_required
def send_test_request():
    """Send test request message"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    
    if not multi_client or session_name not in multi_client.sessions:
        return jsonify({'success': False, 'message': 'Session not available'})
    
    client = multi_client.sessions[session_name]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': 'Session not connected'})
    
    try:
        import time
        test_id = str(int(time.time()))
        success = client.send_custom_message(f'35=1 112={test_id}')  # Test Request
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/can_send_orders')
@api_login_required
def can_send_orders():
    """Check if we can send orders"""
    global multi_client
    if not multi_client:
        return jsonify({'can_send': False, 'reason': 'No client'})
    
    connected_sessions = [name for name, client in multi_client.sessions.items() if client.session_id and client.running]
    return jsonify({
        'can_send': len(connected_sessions) > 0,
        'connected_sessions': connected_sessions,
        'active_session': multi_client.active_session
    })

@app.route('/api/load_config')
@api_login_required
def load_config():
    """Load configuration file"""
    try:
        with open('multi_session_config.json', 'r') as f:
            config = json.load(f)
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/save_config', methods=['POST'])
@api_login_required
def save_config():
    """Save configuration file with backup"""
    try:
        data = request.json
        config_text = data.get('config')
        
        # Validate JSON
        config_data = json.loads(config_text)
        
        # Create backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        user = session.get('user', 'unknown')
        backup_filename = f'multi_session_config_backup_{user}_{timestamp}.json'
        
        # Create backup of current config
        import shutil
        shutil.copy('multi_session_config.json', backup_filename)
        
        # Save new config
        with open('multi_session_config.json', 'w') as f:
            json.dump(config_data, f, indent=2)
        
        return jsonify({
            'success': True, 
            'backup_file': backup_filename,
            'message': 'Configuration saved successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/restart_server', methods=['POST'])
@api_login_required
def restart_server():
    """Restart the server"""
    try:
        import subprocess
        import os
        
        # Log the restart action
        user = session.get('user', 'unknown')
        message_handler.log_message(f"Server restart initiated by user: {user}")
        
        # Start restart script in background
        script_path = os.path.join(os.getcwd(), 'restart_app.sh')
        if os.path.exists(script_path):
            subprocess.Popen(['nohup', 'bash', script_path], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL,
                           preexec_fn=os.setsid)
            return jsonify({'success': True, 'message': 'Server restart initiated'})
        else:
            return jsonify({'success': False, 'message': 'Restart script not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/send_sequence_reset', methods=['POST'])
@api_login_required
def send_sequence_reset():
    """Send sequence reset message"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    new_seq_num = data.get('new_seq_num')
    gap_fill = data.get('gap_fill', False)
    
    if not multi_client or session_name not in multi_client.sessions:
        return jsonify({'success': False, 'message': 'Session not available'})
    
    client = multi_client.sessions[session_name]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': 'Session not connected'})
    
    try:
        success = client.send_sequence_reset(new_seq_num, gap_fill)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get_sequence_numbers', methods=['POST'])
@api_login_required
def get_sequence_numbers():
    """Get current sequence numbers"""
    global multi_client
    data = request.json
    session_name = data.get('session_name')
    
    if not multi_client or session_name not in multi_client.sessions:
        return jsonify({'success': False, 'message': 'Session not available'})
    
    client = multi_client.sessions[session_name]
    if not (client.session_id and client.running):
        return jsonify({'success': False, 'message': 'Session not connected'})
    
    try:
        sender_seq, target_seq = client.get_sequence_numbers()
        return jsonify({
            'success': True,
            'sender_seq': sender_seq,
            'target_seq': target_seq
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/set_sequence_numbers', methods=['POST'])
@api_login_required
def set_sequence_numbers():
    """Set sequence numbers"""
    try:
        data = request.json
        sender_seq = data.get('sender_seq')
        target_seq = data.get('target_seq')
        session_id_str = data.get('session_id')  # Now expecting session_id instead of session_name
        
        if not session_id_str:
            return jsonify({'success': False, 'message': 'No session ID provided'})
        
        if not multi_client:
            return jsonify({'success': False, 'message': 'No multi-client initialized'})
        
        # Find the session name that matches the session_id
        target_session_name = None
        for session_config in multi_client.session_configs:
            config_session_id = f"{session_config['fix_version']}:{session_config['sender_comp_id']}->{session_config['target_comp_id']}"
            if config_session_id == session_id_str:
                target_session_name = session_config['name']
                break
        
        if not target_session_name:
            return jsonify({'success': False, 'message': f'Session config not found for {session_id_str}'})
        
        # Find or create session client
        if target_session_name not in multi_client.sessions:
            # Create session client for sequence number setting
            message_handler.log_message(f"DEBUG: Creating session {target_session_name} for sequence setting")
            success, message = multi_client.connect_session(target_session_name)
            if not success:
                return jsonify({'success': False, 'message': f'Cannot create session {target_session_name}: {message}'})
        
        client = multi_client.sessions[target_session_name]
        message_handler.log_message(f"DEBUG: Using client for session {target_session_name}, session_id: {client.session_id}")
        
        # Ensure session_id is set - create it from config if needed
        if not client.session_id:
            # Find session config and create SessionID
            for config in multi_client.session_configs:
                if config['name'] == target_session_name:
                    client.session_id = fix.SessionID(
                        config['fix_version'],
                        config['sender_comp_id'],
                        config['target_comp_id']
                    )
                    message_handler.log_message(f"DEBUG: Created SessionID object: {client.session_id}")
                    break
            
            if not client.session_id:
                return jsonify({'success': False, 'message': f'Cannot create SessionID for {target_session_name}'})
        
        # Set sequence numbers using QuickFIX client methods
        results = []
        error_msgs = []
        
        message_handler.log_message(f"DEBUG: Setting sequence numbers - sender_seq: {sender_seq}, target_seq: {target_seq}")
        message_handler.log_message(f"DEBUG: Client session_id: {client.session_id}")
        
        if sender_seq:
            try:
                result = client.set_next_sender_seq(sender_seq)
                results.append(result)
                message_handler.log_message(f"Set sender seq {sender_seq}: {result}")
                if not result:
                    error_msgs.append(f"Failed to set sender seq {sender_seq}")
            except Exception as e:
                results.append(False)
                error_msgs.append(f"Exception setting sender seq: {e}")
                message_handler.log_message(f"Exception setting sender seq: {e}")
        
        if target_seq:
            try:
                result = client.set_next_target_seq(target_seq)
                results.append(result)
                message_handler.log_message(f"Set target seq {target_seq}: {result}")
                if not result:
                    error_msgs.append(f"Failed to set target seq {target_seq}")
            except Exception as e:
                results.append(False)
                error_msgs.append(f"Exception setting target seq: {e}")
                message_handler.log_message(f"Exception setting target seq: {e}")
        
        if all(results) and results:
            message_handler.log_message(f"Sequence numbers set for {session_id_str} - Incoming: {target_seq}, Outgoing: {sender_seq}")
            return jsonify({'success': True})
        else:
            error_msg = '; '.join(error_msgs) if error_msgs else 'Unknown error'
            return jsonify({'success': False, 'message': f'Failed to set sequence numbers: {error_msg}'})
        

        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    connected_clients.append(request.sid)
    emit('connected', {'message': 'Connected to SendFix Multi-Session'})
    
    # Join user-specific room if authenticated
    if 'user' in session:
        from flask_socketio import join_room
        join_room(f'user_{session["user"]}')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if request.sid in connected_clients:
        connected_clients.remove(request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8081, debug=True, allow_unsafe_werkzeug=True)