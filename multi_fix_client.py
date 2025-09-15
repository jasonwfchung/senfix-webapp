import quickfix as fix
import json
import os
from quickfix_client import QuickFixClient

class MultiFixClient:
    def __init__(self, message_callback=None, session_callback=None):
        self.message_callback = message_callback
        self.session_callback = session_callback
        self.sessions = {}
        self.active_session = None
        self.session_states = {}  # Track session states
        self.load_session_configs()
        
    def session_state_callback(self, state, session_id):
        """Handle session state changes"""
        session_str = str(session_id)
        self.session_states[session_str] = state
        # Also store by config name for lookup
        for name, client in self.sessions.items():
            if client.session_id and str(client.session_id) == session_str:
                self.session_states[name] = state
                break
        if self.session_callback:
            self.session_callback(state, session_str)
        
    def load_session_configs(self):
        """Load session configurations from JSON file"""
        try:
            with open('multi_session_config.json', 'r') as f:
                config = json.load(f)
                self.session_configs = config['sessions']
        except Exception as e:
            # Fallback to default sessions
            self.session_configs = [
                {
                    "name": "LQNT UAT",
                    "server_ip": "hk1qvphxcrt01",
                    "port": 5731,
                    "fix_version": "FIX.4.2",
                    "sender_comp_id": "JCHUNG",
                    "target_comp_id": "LQNTHKUAT",
                    "heartbeat_interval": 30
                }
            ]
            
    def get_session_names(self):
        """Get list of available session names"""
        return [session['name'] for session in self.session_configs]
        
    def connect_session(self, session_name):
        """Connect to a specific session"""
        try:
            # Check if already connected to this session
            if session_name in self.sessions:
                client = self.sessions[session_name]
                if client.is_connected():
                    self.active_session = session_name
                    return True, f"Already connected to {session_name}"
                else:
                    # Properly disconnect and clean up old session
                    client.disconnect()
                    del self.sessions[session_name]
            
            # Find session config
            session_config = None
            for config in self.session_configs:
                if config['name'] == session_name:
                    session_config = config
                    break
                    
            if not session_config:
                return False, f"Session {session_name} not found"
                
            # Determine connection type
            connection_type = session_config.get('connection_type', 'initiator')
            
            # Create new client with session config (don't disconnect others)
            client = QuickFixClient(self.message_callback, self.session_state_callback, connection_type)
            client.gui_callback = self.message_callback  # Set GUI callback for execution reports
            
            # Override config with session-specific values
            client.HOST = session_config.get('server_ip', 'localhost')  # Acceptors don't need server_ip
            client.PORT = session_config['port']
            client.FIX_VERSION = session_config['fix_version']
            client.SENDERCOMPID = session_config['sender_comp_id']
            client.TARGETCOMPID = session_config['target_comp_id']
            client.HEARTBEAT = session_config['heartbeat_interval']
            
            # Apply session-specific QuickFIX overrides if present
            if 'quickfix_overrides' in session_config:
                client.quickfix_overrides = session_config['quickfix_overrides']
            
            # Connect without timeout checks
            client.connect()
            self.sessions[session_name] = client
            self.active_session = session_name
            return True, f"Connecting to {session_name}..."
                
        except Exception as e:
            return False, f"Error connecting to {session_name}: {e}"
            
    def disconnect_current(self):
        """Disconnect current active session"""
        if self.active_session and self.active_session in self.sessions:
            self.sessions[self.active_session].disconnect()
            del self.sessions[self.active_session]
            self.active_session = None
            
    def disconnect_session(self, session_name):
        """Disconnect specific session"""
        if session_name in self.sessions:
            self.sessions[session_name].disconnect()
            del self.sessions[session_name]
            if self.active_session == session_name:
                self.active_session = None
                
    def get_all_sessions(self):
        """Get all connected sessions"""
        connected_sessions = {}
        for name, client in self.sessions.items():
            if client.is_connected():
                connected_sessions[name] = client
        return connected_sessions
            
    def get_current_client(self):
        """Get current active client"""
        if self.active_session and self.active_session in self.sessions:
            return self.sessions[self.active_session]
        return None
        
    def get_current_session_info(self):
        """Get current session information"""
        if self.active_session:
            client = self.get_current_client()
            if client:
                return {
                    'name': self.active_session,
                    'host': client.HOST,
                    'port': client.PORT,
                    'sender': client.SENDERCOMPID,
                    'target': client.TARGETCOMPID,
                    'connected': client.is_connected()
                }
        return None
        
    def is_connected(self):
        """Check if current session is connected"""
        if not self.active_session:
            return False
        client = self.get_current_client()
        if not client:
            return False
        return client.is_connected()
        
    def is_session_connected(self, session_name):
        """Check if specific session is connected"""
        if session_name in self.sessions:
            return self.sessions[session_name].is_connected()
        return False