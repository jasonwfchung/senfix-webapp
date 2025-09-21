import quickfix as fix
import threading
import time
import logging
import configparser
from datetime import datetime
import json
import os

class QuickFixClient(fix.Application):
    def __init__(self, message_callback=None, session_callback=None, connection_type='initiator'):
        super().__init__()
        self.message_callback = message_callback
        self.session_callback = session_callback
        self.connection_type = connection_type
        self.setup_logging()
        self.load_config()
        self.session_id = None
        self.order_counter = 0
        self.running = False
        self.logged_on = False
        self.connection_failed = False
        self.quickfix_overrides = {}
        self.connection_count = 0
        
    def setup_logging(self):
        logging.basicConfig(
            filename='sendfix_quickfix.log',
            level=logging.DEBUG,
            format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        config = configparser.ConfigParser()
        config.read('sendfix.cfg')
        if 'DEFAULT' in config:
            try:
                self.HOST = config['DEFAULT']['ServerIP']
                self.PORT = int(config['DEFAULT']['Port'])
                self.FIX_VERSION = config['DEFAULT']['FixVersion']
                self.SENDERCOMPID = config['DEFAULT']['SenderCompId']
                self.TARGETCOMPID = config['DEFAULT']['TargetCompId']
                self.HEARTBEAT = int(config['DEFAULT']['HeartbeatInterval'])
            except Exception as e:
                raise Exception(f"Invalid configuration: {e}")
                
    def log_message(self, message):
        self.logger.info(message)
        if self.message_callback:
            self.message_callback(message)
            
    def load_default_config(self):
        """Load default QuickFIX configuration"""
        try:
            with open('quickfix_defaults.json', 'r') as f:
                return json.load(f)
        except:
            # Fallback defaults if file doesn't exist
            return {
                "ConnectionType": "initiator",
                "ReconnectInterval": "60",
                "FileStorePath": "store",
                "FileLogPath": "log",
                "StartTime": "00:00:00",
                "EndTime": "00:00:00",
                "UseDataDictionary": "N",
                "DefaultApplVerID": "FIX.4.2",
                "SendRedundantResendRequests": "N"
            }
    
    def create_config_file(self):
        """Create QuickFIX configuration file with defaults and overrides"""
        defaults = self.load_default_config()
        
        # Apply session-specific overrides to defaults
        if hasattr(self, 'quickfix_overrides') and self.quickfix_overrides:
            defaults.update(self.quickfix_overrides)
        
        # Set connection type in defaults
        if self.connection_type == 'acceptor':
            defaults["ConnectionType"] = "acceptor"
        else:
            defaults["ConnectionType"] = "initiator"
            
        # FIX standard compliant settings - no sequence resets
        defaults.update({
            "ReconnectInterval": "30",
            "ResetOnLogon": "N", 
            "ResetOnLogout": "N",
            "ResetOnDisconnect": "N",
            "ResetSeqNumFlag": "N",
            "RefreshOnLogon": "N",
            "PersistMessages": "Y"
        })
        
        # Build DEFAULT section
        default_section = "[DEFAULT]\n"
        for key, value in defaults.items():
            default_section += f"{key}={value}\n"
        
        # Build SESSION section based on connection type
        if self.connection_type == 'acceptor':
            session_section = f"""\n[SESSION]
BeginString={self.FIX_VERSION}
SenderCompID={self.SENDERCOMPID}
TargetCompID={self.TARGETCOMPID}
SocketAcceptPort={self.PORT}
HeartBtInt={self.HEARTBEAT}
"""
        else:
            session_section = f"""\n[SESSION]
BeginString={self.FIX_VERSION}
SenderCompID={self.SENDERCOMPID}
TargetCompID={self.TARGETCOMPID}
SocketConnectPort={self.PORT}
SocketConnectHost={self.HOST}
HeartBtInt={self.HEARTBEAT}
"""
        
        config_content = default_section + session_section
        
        # Log the configuration being used
        self.log_message(f"Creating QuickFIX config: {self.SENDERCOMPID}->{self.TARGETCOMPID} at {self.HOST}:{self.PORT}")
        self.log_message(f"Heartbeat interval: {self.HEARTBEAT} seconds")
        
        with open('quickfix_client.cfg', 'w') as f:
            f.write(config_content)
            
    def connect(self):
        try:
            # CRITICAL: Track connection attempts
            self.connection_count += 1
            self.log_message(f"*** CONNECTION ATTEMPT #{self.connection_count} ***")
            
            # CRITICAL: Ensure clean state before connecting
            self.session_id = None
            self.logged_on = False
            self.running = False
            self.connection_failed = False
            
            self.create_config_file()
            
            # Create directories if they don't exist
            os.makedirs('store', exist_ok=True)
            os.makedirs('log', exist_ok=True)
            
            # Check existing sequence numbers before connecting
            session_qualifier = f"{self.FIX_VERSION}:{self.SENDERCOMPID}->{self.TARGETCOMPID}"
            store_files = [
                f"store/{session_qualifier}.seqnums",
                f"store/{session_qualifier}.session"
            ]
            
            for store_file in store_files:
                if os.path.exists(store_file):
                    self.log_message(f"*** Found existing store file: {store_file} ***")
                    try:
                        with open(store_file, 'r') as f:
                            content = f.read()
                            self.log_message(f"*** Store content: {content[:100]}... ***")
                    except:
                        pass
                else:
                    self.log_message(f"*** Store file not found: {store_file} ***")
            
            # CRITICAL: Create fresh QuickFIX objects for each connection
            self.log_message(f"*** CREATING FRESH QUICKFIX OBJECTS ***")
            settings = fix.SessionSettings('quickfix_client.cfg')
            store_factory = fix.FileStoreFactory(settings)
            log_factory = fix.FileLogFactory(settings)
            
            if self.connection_type == 'acceptor':
                self.log_message(f"*** ACCEPTOR: Creating SocketAcceptor for port {self.PORT} ***")
                self.acceptor = fix.SocketAcceptor(self, store_factory, settings, log_factory)
                self.log_message(f"*** ACCEPTOR: Starting acceptor... ***")
                self.acceptor.start()
                self.running = True
                self.log_message(f"*** ACCEPTOR: Started successfully, listening on port {self.PORT} ***")
                self.log_message(f"*** ACCEPTOR: Ready to accept connections from {self.TARGETCOMPID} ***")
                
                # Check if port is actually bound
                import socket
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    result = sock.connect_ex(('localhost', self.PORT))
                    sock.close()
                    if result == 0:
                        self.log_message(f"*** ACCEPTOR: Port {self.PORT} is OPEN and accepting connections ***")
                    else:
                        self.log_message(f"*** ACCEPTOR: Port {self.PORT} connection test failed (code: {result}) ***")
                except Exception as e:
                    self.log_message(f"*** ACCEPTOR: Port check error: {e} ***")
            else:
                # CRITICAL: Force cleanup of old initiator
                if hasattr(self, 'initiator'):
                    self.log_message(f"*** DESTROYING OLD INITIATOR ***")
                    try:
                        self.initiator.stop()
                        time.sleep(0.2)
                    except:
                        pass
                    del self.initiator
                    import gc
                    gc.collect()
                    
                self.log_message(f"*** CREATING FRESH INITIATOR ***")
                self.initiator = fix.SocketInitiator(self, store_factory, settings, log_factory)
                self.initiator.start()
                self.running = True
                self.log_message(f"QuickFIX client started, connecting to {self.HOST}:{self.PORT}")
            return True
            
        except Exception as e:
            self.log_message(f"Connection failed: {e}")
            return False
            
    def reset_sequence_numbers(self):
        """Reset sequence numbers to 1 for both sender and target"""
        try:
            if self.session_id:
                self.set_next_sender_seq(1)
                self.set_next_target_seq(1)
                self.log_message("Sequence numbers reset to 1")
                return True
        except Exception as e:
            self.log_message(f"Error resetting sequence numbers: {e}")
        return False
            
    def disconnect(self):
        try:
            # CRITICAL: Force logout before disconnect to clean QuickFIX state
            if self.session_id and self.logged_on:
                self.log_message(f"*** FORCING LOGOUT BEFORE DISCONNECT: {self.session_id} ***")
                try:
                    fix.Session.logout(self.session_id)
                    time.sleep(0.5)  # Allow logout to complete
                except Exception as e:
                    self.log_message(f"*** LOGOUT ERROR: {e} ***")
            
            if self.connection_type == 'acceptor' and hasattr(self, 'acceptor') and self.running:
                self.log_message(f"*** ACCEPTOR: Stopping acceptor on port {self.PORT} ***")
                self.acceptor.stop()
                self.log_message(f"*** ACCEPTOR: Stopped successfully ***")
                del self.acceptor
            elif hasattr(self, 'initiator') and self.running:
                self.log_message("*** INITIATOR: Stopping initiator ***")
                self.initiator.stop()
                time.sleep(0.5)  # Allow stop to complete
                del self.initiator
                
            self.running = False
            self.logged_on = False
            self.logon_count = 0  # Reset logon counter
            
            # CRITICAL: Clear session_id on disconnect to prevent stale references
            if self.session_id:
                self.log_message(f"*** CLEARING SESSION_ID: {self.session_id} ***")
                self.session_id = None
                
            # CRITICAL: Force cleanup of QuickFIX internal state
            import gc
            gc.collect()
            self.log_message(f"*** DISCONNECT COMPLETE - QuickFIX state cleared ***")
        except Exception as e:
            self.log_message(f"Disconnect error: {e}")
            
    # QuickFIX Application callbacks
    def onCreate(self, sessionID):
        # CRITICAL: Do NOT set session_id here - only in onLogon when actually connected
        # Clear any stale session_id to prevent confusion
        if self.session_id:
            self.log_message(f"*** CLEARING STALE SESSION_ID: {self.session_id} ***")
            self.session_id = None
        
        # CRITICAL: Reset all state for fresh session
        self.logged_on = False
        self.connection_failed = False
        self.logon_count = 0
        
        self.log_message(f"*** SESSION LIFECYCLE: onCreate() called for {sessionID} ***")
        self.log_message(f"*** CONNECTION #{self.connection_count} - FRESH SESSION CREATED ***")
        self.log_message(f"*** SESSION_ID NOT SET - waiting for onLogon() ***")
        self.log_message(f"Session created: {sessionID}")
        
    def onLogon(self, sessionID):
        self.logged_on = True
        self.connection_failed = False
        self.logon_time = time.time()  # Track logon time
        
        # CRITICAL: Set session_id ONLY on successful logon - this is the ONLY valid session
        old_session_id = self.session_id
        self.session_id = sessionID
        
        self.log_message(f"*** SESSION LIFECYCLE: onLogon() called for {sessionID} ***")
        self.log_message(f"*** SESSION ID SET ON LOGON: {old_session_id} -> {sessionID} ***")
        self.log_message(f"*** THIS IS THE ONLY VALID SESSION FOR ORDERS ***")
        self.log_message(f"*** SESSION STATE: logged_on={self.logged_on}, running={self.running} ***")
        self.log_message(f"*** LOGON SESSION OBJECT ID: {id(sessionID)} ***")
        self.log_message(f"*** CLIENT OBJECT ID AT LOGON: {id(self)} ***")
        
        # Give QuickFIX time to fully initialize the session
        time.sleep(0.2)  # Allow QuickFIX internal state to sync
        
        # Verify session exists in registry (but don't trust isLoggedOn check)
        try:
            session = fix.Session.lookupSession(sessionID)
            if session:
                self.log_message(f"*** SUCCESS: Session found in QuickFIX registry ***")
                self.log_message(f"*** TRUSTING onLogon() CALLBACK - session is ready for orders ***")
            else:
                self.log_message(f"*** ERROR: Session not found in QuickFIX registry ***")
        except Exception as e:
            self.log_message(f"*** ERROR checking QuickFIX session registry: {e} ***")
        
        self.log_message(f"Logon successful: {sessionID}")
        
        if hasattr(self, 'session_callback'):
            self.session_callback('connected', sessionID)
        
    def onLogout(self, sessionID):
        self.logged_on = False
        self.log_message(f"*** SESSION LIFECYCLE: onLogout() called for {sessionID} ***")
        self.log_message(f"*** SESSION STATE: logged_on={self.logged_on}, running={self.running} ***")
        
        # CRITICAL: Clear session_id on logout to prevent stale references
        if self.session_id:
            self.log_message(f"*** CLEARING SESSION_ID ON LOGOUT: {self.session_id} ***")
            self.session_id = None
        else:
            self.log_message(f"*** SESSION_ID ALREADY CLEARED ***")
        
        # CRITICAL: Reset logon counter for fresh reconnection
        self.logon_count = 0
        self.log_message(f"*** RESET LOGON COUNTER FOR FRESH RECONNECTION ***")
        
        # Check if this is an immediate logout after logon (connection rejected)
        if hasattr(self, 'logon_time'):
            logout_time = time.time()
            duration = logout_time - self.logon_time
            self.log_message(f"*** SESSION DURATION: {duration:.2f} seconds ***")
            if duration < 2:  # Less than 2 seconds
                self.log_message(f"*** IMMEDIATE LOGOUT DETECTED - Connection rejected by server ***")
                self.log_message(f"*** Possible causes: Invalid credentials, session not configured on server, or heartbeat mismatch ***")
        
        # Check if initiator is trying to reconnect
        if hasattr(self, 'initiator') and self.running:
            self.log_message(f"*** INITIATOR STATUS: Still running, may attempt reconnect ***")
        
        self.log_message(f"Logout: {sessionID} - Session disconnected by counterparty")
        
        if hasattr(self, 'session_callback'):
            self.session_callback('disconnected', sessionID)
        
    def toAdmin(self, message, sessionID):
        msg_type_field = fix.MsgType()
        message.getHeader().getField(msg_type_field)
        msg_type = msg_type_field.getValue()
        
        # Remove ResetSeqNumFlag from logon messages
        if msg_type == 'A':  # Logon
            try:
                if message.isSetField(141):  # ResetSeqNumFlag
                    message.removeField(141)
                    self.log_message(f"*** REMOVED Tag 141 from logon message ***")
            except:
                pass
                
            if hasattr(self, 'logon_count'):
                self.logon_count += 1
                self.log_message(f"*** LOGON ATTEMPT #{self.logon_count} ***")
                if self.logon_count > 1:
                    self.log_message(f"*** WARNING: Multiple logon attempts detected ***")
                    self.log_message(f"*** Connection #{self.connection_count} - Logon attempt #{self.logon_count} ***")
                    self.log_message(f"*** Session state - logged_on: {self.logged_on}, running: {self.running} ***")
                    
                    # Check why we're sending another logon
                    try:
                        session = fix.Session.lookupSession(sessionID)
                        if session:
                            qf_logged_on = session.isLoggedOn()
                            self.log_message(f"*** QuickFIX thinks logged_on: {qf_logged_on} ***")
                        else:
                            self.log_message(f"*** QuickFIX session not found ***")
                    except Exception as e:
                        self.log_message(f"*** Error checking session: {e} ***")
            else:
                self.logon_count = 1
                self.log_message(f"*** FIRST LOGON ATTEMPT ***")
                self.log_message(f"*** CONNECTION #{self.connection_count} - FRESH LOGON ***")
        elif msg_type == '0':  # Heartbeat
            self.log_message(f"*** HEARTBEAT SENT - Session appears active ***")
            # Verify session is still valid during heartbeat
            try:
                if self.session_id:
                    session_obj = fix.Session.lookupSession(self.session_id)
                    if not session_obj:
                        self.log_message(f"*** CRITICAL: Session lost during heartbeat - {self.session_id} ***")
                        self.logged_on = False
                        self.session_id = None
            except Exception as e:
                self.log_message(f"*** Heartbeat session check error: {e} ***")
                
        self.log_message(f"Sent Admin ({msg_type}): {self.format_message(message)}")
        
    def fromAdmin(self, message, sessionID):
        msg_type_field = fix.MsgType()
        message.getHeader().getField(msg_type_field)
        msg_type = msg_type_field.getValue()
        
        # Handle different admin message types
        if msg_type == '3':  # Reject
            self.connection_failed = True
            self.logged_on = False
            self.log_message(f"*** REJECT RECEIVED - Connection failed ***")
            # Get reject reason if available
            try:
                text_field = fix.Text()
                if message.isSetField(text_field):
                    message.getField(text_field)
                    self.log_message(f"*** Reject reason: {text_field.getValue()} ***")
            except:
                pass
        elif msg_type == '2':  # ResendRequest
            self.log_message(f"*** RESEND REQUEST - Sequence number issue detected ***")
        elif msg_type == '4':  # SequenceReset
            self.log_message(f"*** SEQUENCE RESET - Adjusting sequence numbers ***")
        elif msg_type == '0':  # Heartbeat
            self.log_message(f"*** HEARTBEAT RECEIVED - Session active ***")
            # Confirm session is still valid on heartbeat receipt
            try:
                if self.session_id:
                    session_obj = fix.Session.lookupSession(self.session_id)
                    if session_obj:
                        self.log_message(f"*** HEARTBEAT CONFIRMS: Session {self.session_id} still valid ***")
                    else:
                        self.log_message(f"*** HEARTBEAT WARNING: Session {self.session_id} not found ***")
            except Exception as e:
                self.log_message(f"*** Heartbeat validation error: {e} ***")
        elif msg_type == '5':  # Logout
            self.log_message(f"*** LOGOUT MESSAGE RECEIVED ***")
            
        self.log_message(f"Received Admin ({msg_type}): {self.format_message(message)}")
        
    def toApp(self, message, sessionID):
        msg_type_field = fix.MsgType()
        message.getHeader().getField(msg_type_field)
        msg_type = msg_type_field.getValue()
        msg_desc = self.get_message_type_description(msg_type)
        self.log_message(f"Sent {msg_desc}: {self.format_message(message)}")
        
    def fromApp(self, message, sessionID):
        msg_type_field = fix.MsgType()
        message.getHeader().getField(msg_type_field)
        msg_type = msg_type_field.getValue()
        msg_desc = self.get_message_type_description(msg_type)
        formatted_msg = self.format_message(message)
        self.log_message(f"Received {msg_desc}: {formatted_msg}")
        
        # Handle execution reports for GUI
        if msg_type == fix.MsgType_ExecutionReport and hasattr(self, 'gui_callback') and self.gui_callback:
            self.gui_callback(formatted_msg)
            
    def send_new_order_single(self, symbol, side, quantity, price=None, order_type='1', tif='0', custom_tags=None):
        """Send New Order Single with proper header field handling"""
        try:
            if not self.session_id:
                self.log_message("No active session")
                return False, None
                
            message = fix.Message()
            header = message.getHeader()
            
            # Header
            header.setField(fix.BeginString(self.FIX_VERSION))
            header.setField(fix.MsgType(fix.MsgType_NewOrderSingle))
            
            # Generate ClOrdID
            clordid = self.generate_clordid()
            message.setField(fix.ClOrdID(clordid))
            message.setField(fix.Symbol(symbol))
            message.setField(fix.Side(side))
            message.setField(fix.OrderQty(int(quantity)))
            message.setField(fix.OrdType(order_type))
            message.setField(fix.TimeInForce(tif))
            message.setField(fix.HandlInst('1'))
            message.setField(fix.TransactTime())  # Tag 60
            
            # Price for limit orders
            if price and order_type == '2':
                message.setField(fix.Price(float(price)))
                
            # Add custom tags with proper header field handling
            if custom_tags:
                for tag_value in custom_tags.split('|'):
                    if '=' in tag_value:
                        tag, value = tag_value.split('=', 1)
                        tag_int = int(tag)
                        
                        # Set routing fields in header for proper FIX routing
                        if tag_int == 50:  # SenderSubID - header field for routing
                            header.setField(fix.SenderSubID(value))
                            self.log_message(f"Set SenderSubID (Tag 50) in header: {value}")
                        elif tag_int == 115:  # OnBehalfOfCompID - header field for routing
                            header.setField(fix.OnBehalfOfCompID(value))
                            self.log_message(f"Set OnBehalfOfCompID (Tag 115) in header: {value}")
                        else:
                            # Other tags go in message body
                            message.setField(tag_int, value)
                        
            # Trust only our internal state - ignore QuickFIX isLoggedOn() due to stale session_id issues
            if not (self.logged_on and self.running):
                self.log_message(f"*** PRE-SEND ERROR: Session not ready (logged_on={self.logged_on}, running={self.running}) ***")
                return False, None
                
            # CRITICAL: Double-check session is still valid before sending
            try:
                session_obj = fix.Session.lookupSession(self.session_id)
                if not session_obj:
                    self.log_message(f"*** CRITICAL ERROR: Session {self.session_id} not found in QuickFIX registry ***")
                    self.log_message(f"*** This indicates a stale session - forcing reconnection ***")
                    self.logged_on = False
                    self.session_id = None
                    return False, None
                    
                # Additional check: verify session is actually connected to network
                if not session_obj.isLoggedOn():
                    self.log_message(f"*** CRITICAL ERROR: QuickFIX session shows not logged on ***")
                    self.log_message(f"*** Session state mismatch - our logged_on={self.logged_on}, QuickFIX={session_obj.isLoggedOn()} ***")
                    # Don't fail here - trust our callback, but log the discrepancy
                    
            except Exception as e:
                self.log_message(f"*** SESSION VALIDATION ERROR: {e} ***")
                return False, None
            
            # CRITICAL: Use the EXACT SessionID object from logon - do NOT create fresh one
            self.log_message(f"*** USING LOGON SESSION_ID: {self.session_id} ***")
            self.log_message(f"*** LOGON SESSION OBJECT ID: {id(self.session_id)} ***")
            self.log_message(f"*** CLIENT OBJECT ID AT SEND: {id(self)} ***")
            self.log_message(f"*** QUICKFIX SESSION OBJECT ID: {id(session_obj)} ***")
            self.log_message(f"*** PROCEEDING WITH ORDER SEND ***")
            
            result = fix.Session.sendToTarget(message, self.session_id)
            self.log_message(f"*** SEND RESULT: sendToTarget returned {result} ***")
            
            if not result:
                self.log_message(f"*** SEND FAILED: sendToTarget returned False - message not transmitted ***")
                return False, None
                
            return True, clordid
        except Exception as e:
            self.log_message(f"Error sending order: {e}")
            return False, None
            
    def send_order_cancel_request(self, orig_clordid, symbol, side, quantity):
        """Send Order Cancel Request"""
        try:
            if not self.session_id:
                self.log_message("No active session")
                return False
                
            message = fix.Message()
            header = message.getHeader()
            
            header.setField(fix.BeginString(self.FIX_VERSION))
            header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))
            
            message.setField(fix.ClOrdID(self.generate_clordid()))
            message.setField(fix.OrigClOrdID(orig_clordid))
            message.setField(fix.Symbol(symbol))
            message.setField(fix.Side(side))
            message.setField(fix.OrderQty(int(quantity)))
            message.setField(fix.TransactTime())  # Tag 60
            
            fix.Session.sendToTarget(message, self.session_id)
            return True
        except Exception as e:
            self.log_message(f"Error sending cancel: {e}")
            return False
            
    def send_order_cancel_replace_request(self, orig_clordid, symbol, side, quantity, price=None, order_type='1', tif='0'):
        """Send Order Cancel/Replace Request"""
        try:
            if not self.session_id:
                self.log_message("No active session")
                return False
                
            message = fix.Message()
            header = message.getHeader()
            
            header.setField(fix.BeginString(self.FIX_VERSION))
            header.setField(fix.MsgType(fix.MsgType_OrderCancelReplaceRequest))
            
            message.setField(fix.ClOrdID(self.generate_clordid()))
            message.setField(fix.OrigClOrdID(orig_clordid))
            message.setField(fix.Symbol(symbol))
            message.setField(fix.Side(side))
            message.setField(fix.OrderQty(int(quantity)))
            message.setField(fix.OrdType(order_type))
            message.setField(fix.TimeInForce(tif))
            message.setField(fix.HandlInst('1'))
            message.setField(fix.TransactTime())  # Tag 60
            
            if price and order_type == '2':
                message.setField(fix.Price(float(price)))
                
            fix.Session.sendToTarget(message, self.session_id)
            return True
        except Exception as e:
            self.log_message(f"Error sending replace: {e}")
            return False
            
    def send_raw_fix(self, raw_fix):
        """Send raw FIX message"""
        try:
            if not self.session_id:
                self.log_message("No active session")
                return False
                
            pairs = raw_fix.split("|")
            message = fix.Message()
            header = message.getHeader()
            
            msg_type = None
            for pair in pairs:
                if '=' in pair:
                    tag, value = pair.split('=', 1)
                    tag_int = int(tag)
                    
                    if tag_int == 35:  # MsgType - required
                        msg_type = value
                        header.setField(fix.MsgType(value))
                    elif tag_int == 8:  # BeginString - let QuickFIX handle
                        continue
                    elif tag_int in [9, 10, 34, 52]:  # Skip auto-generated fields
                        continue
                    elif tag_int == 49:  # SenderCompID - optional override
                        header.setField(fix.SenderCompID(value))
                    elif tag_int == 56:  # TargetCompID - optional override
                        header.setField(fix.TargetCompID(value))
                    elif tag_int == 50:  # SenderSubID - header field for routing
                        header.setField(fix.SenderSubID(value))
                    elif tag_int == 115:  # OnBehalfOfCompID - header field for routing
                        header.setField(fix.OnBehalfOfCompID(value))
                    else:
                        message.setField(tag_int, value)
                        
            if msg_type:
                fix.Session.sendToTarget(message, self.session_id)
                return True
            else:
                self.log_message("Error: No message type found in raw FIX")
                return False
        except Exception as e:
            self.log_message(f"Error sending raw FIX: {e}")
            return False
            
    def send_custom_message(self, custom_msg):
        """Send custom message from space-separated tag=value pairs"""
        try:
            if not self.session_id:
                self.log_message("No active session")
                return False
                
            pairs = custom_msg.split()
            message = fix.Message()
            header = message.getHeader()
            
            msg_type = None
            for pair in pairs:
                if '=' in pair:
                    tag, value = pair.split('=', 1)
                    tag_int = int(tag)
                    
                    if tag_int == 35:  # MsgType
                        msg_type = value
                        header.setField(fix.MsgType(value))
                    elif tag_int == 8:  # BeginString
                        header.setField(fix.BeginString(value))
                    elif tag_int in [49, 56, 34, 52]:  # Skip header fields
                        continue
                    else:
                        message.setField(tag_int, value)
                        
            if msg_type:
                fix.Session.sendToTarget(message, self.session_id)
                return True
            else:
                self.log_message("Error: No message type found")
                return False
        except Exception as e:
            self.log_message(f"Error sending custom message: {e}")
            return False
            
    def send_orders_from_file(self, filename='fix_orders.txt'):
        """Send orders from file"""
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
                
            header = lines[0].strip().split('|')
            self.log_message(f"Processing {len(lines) - 1} orders from {filename}")
            
            for i, line in enumerate(lines[1:], 1):
                if not line.strip():
                    continue
                    
                values = line.strip().split('|')
                message = fix.Message()
                msg_header = message.getHeader()
                
                msg_header.setField(fix.BeginString(self.FIX_VERSION))
                msg_header.setField(fix.MsgType(fix.MsgType_NewOrderSingle))
                
                message.setField(fix.ClOrdID(self.generate_clordid()))
                message.setField(fix.HandlInst('1'))
                
                # Map file data to FIX tags
                for tag, value in zip(header, values):
                    if value:
                        tag_int = int(tag)
                        if tag_int == 48:  # SecurityID
                            message.setField(fix.SecurityID(value))
                            message.setField(fix.Symbol(value))
                        else:
                            message.setField(tag_int, value)
                            
                # Add TransactTime for all orders
                message.setField(fix.TransactTime())  # Tag 60
                            
                fix.Session.sendToTarget(message, self.session_id)
                clord_id = message.getField(fix.ClOrdID())
                self.log_message(f"Sent NewOrderSingle #{i} (ClOrdID={clord_id})")
                time.sleep(0.1)
                
            self.log_message(f"Completed sending {len(lines) - 1} orders")
        except Exception as e:
            self.log_message(f"Error processing orders file: {e}")
            
    def generate_clordid(self):
        self.order_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}{self.order_counter:04d}"
        
    def format_message(self, message):
        """Format QuickFIX message for display"""
        try:
            formatted_pairs = []
            
            # Get header fields including routing fields
            header = message.getHeader()
            for field_tag in [8, 9, 35, 49, 56, 50, 115, 34, 52]:
                try:
                    if field_tag == 8:
                        field = fix.BeginString()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                    elif field_tag == 35:
                        field = fix.MsgType()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                    elif field_tag == 49:
                        field = fix.SenderCompID()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                    elif field_tag == 56:
                        field = fix.TargetCompID()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                    elif field_tag == 50:
                        field = fix.SenderSubID()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                    elif field_tag == 115:
                        field = fix.OnBehalfOfCompID()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                    elif field_tag == 34:
                        field = fix.MsgSeqNum()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                    elif field_tag == 52:
                        field = fix.SendingTime()
                        header.getField(field)
                        formatted_pairs.append(f"{field_tag}={field.getValue()}")
                except:
                    pass
                    
            # Get body fields
            iterator = message.iterator()
            while iterator.hasNext():
                field = iterator.next()
                tag = field.getTag()
                value = field.getValue()
                formatted_pairs.append(f"{tag}={value}")
                
            # Get trailer fields
            trailer = message.getTrailer()
            try:
                checksum_field = fix.CheckSum()
                trailer.getField(checksum_field)
                formatted_pairs.append(f"10={checksum_field.getValue()}")
            except:
                pass
                
            return "|".join(formatted_pairs)
        except Exception as e:
            return str(message)
            
    def get_message_type_description(self, msg_type):
        """Get human-readable description for message type"""
        msg_types = {
            '0': 'Heartbeat',
            '1': 'TestRequest',
            '2': 'ResendRequest',
            '3': 'Reject',
            '4': 'SequenceReset',
            '5': 'Logout',
            'A': 'Logon',
            'D': 'NewOrderSingle',
            'F': 'OrderCancelRequest',
            'G': 'OrderCancelReplaceRequest',
            '8': 'ExecutionReport',
            '9': 'OrderCancelReject'
        }
        return msg_types.get(msg_type, f'MsgType({msg_type})')
        
    def is_connected(self):
        """Check if session is connected - trust our onLogon callback over QuickFIX isLoggedOn"""
        if not self.running:
            return False
            
        # For acceptors, running=True means listening (ready)
        if self.connection_type == 'acceptor':
            return self.running  # Acceptor is "connected" when listening
            
        # For initiators, need actual logon
        if not self.session_id:
            return False
            
        # Trust our logged_on flag from onLogon callback - QuickFIX isLoggedOn() has timing issues
        return self.logged_on and self.running
        
    def send_sequence_reset(self, new_seq_num, gap_fill=False):
        """Send sequence reset message"""
        try:
            if not self.session_id:
                self.log_message("No active session")
                return False
                
            message = fix.Message()
            header = message.getHeader()
            
            header.setField(fix.BeginString(self.FIX_VERSION))
            header.setField(fix.MsgType(fix.MsgType_SequenceReset))
            
            message.setField(fix.NewSeqNo(int(new_seq_num)))
            if gap_fill:
                message.setField(fix.GapFillFlag('Y'))
            else:
                message.setField(fix.GapFillFlag('N'))
                
            fix.Session.sendToTarget(message, self.session_id)
            self.log_message(f"Sent SequenceReset: NewSeqNo={new_seq_num}, GapFill={gap_fill}")
            return True
        except Exception as e:
            self.log_message(f"Error sending sequence reset: {e}")
            return False
            
    def get_sequence_numbers(self):
        """Get current sequence numbers"""
        try:
            if not self.session_id:
                return None, None
                
            next_sender_seq = fix.Session.getExpectedSenderNum(self.session_id)
            next_target_seq = fix.Session.getExpectedTargetNum(self.session_id)
            
            return next_sender_seq, next_target_seq
        except Exception as e:
            self.log_message(f"Error getting sequence numbers: {e}")
            return None, None
            
    def set_next_sender_seq(self, seq_num):
        """Set next outgoing sequence number"""
        try:
            if not self.session_id:
                self.log_message("No active session for setting sender sequence")
                return False
                
            self.log_message(f"DEBUG: session_id type: {type(self.session_id)}, value: {self.session_id}")
            
            # Use the correct QuickFIX API method
            session = fix.Session.lookupSession(self.session_id)
            if session:
                session.setNextSenderMsgSeqNum(int(seq_num))
                self.log_message(f"Set next sender sequence number to: {seq_num}")
                return True
            else:
                self.log_message("Session not found for setting sender sequence")
                return False
        except Exception as e:
            self.log_message(f"Error setting sender sequence: {e}")
            return False
            
    def set_next_target_seq(self, seq_num):
        """Set next expected incoming sequence number"""
        try:
            if not self.session_id:
                self.log_message("No active session for setting target sequence")
                return False
                
            self.log_message(f"DEBUG: session_id type: {type(self.session_id)}, value: {self.session_id}")
            
            # Use the correct QuickFIX API method
            session = fix.Session.lookupSession(self.session_id)
            if session:
                session.setNextTargetMsgSeqNum(int(seq_num))
                self.log_message(f"Set next target sequence number to: {seq_num}")
                return True
            else:
                self.log_message("Session not found for setting target sequence")
                return False
        except Exception as e:
            self.log_message(f"Error setting target sequence: {e}")
            return False