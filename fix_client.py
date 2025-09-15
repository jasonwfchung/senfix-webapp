import socket
import simplefix
import logging
import time
import threading
import configparser
import json
import os
from datetime import datetime

class FixClient:
    def __init__(self, message_callback=None):
        self.message_callback = message_callback
        self.setup_logging()
        self.load_config()
        self.init_variables()
        self.sock = None
        self.running = False
        
    def setup_logging(self):
        logging.basicConfig(
            filename='sendfix.log',
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
                self.HEARTBEAT = config['DEFAULT']['HeartbeatInterval']
            except Exception as e:
                raise Exception(f"Invalid configuration: {e}")
                
    def init_variables(self):
        self.seq = 0
        self.incoming_seq = 0
        self.order_counter = 0
        self.sent_messages = {}
        self.expected_seq = 1
        self.SESSION_FILE = 'session_state.json'
        self.load_session_state()
        
    def log_message(self, message):
        self.logger.info(message)
        if self.message_callback:
            self.message_callback(message)
            
    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.HOST, self.PORT))
            self.running = True
            self.log_message(f"Connected to {self.HOST}:{self.PORT}")
            
            # Start receiver thread
            self.receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.receiver_thread.start()
            
            # Send logon
            self.send_logon()
            return True
        except Exception as e:
            self.log_message(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        self.running = False
        if self.sock:
            self.sock.close()
        self.log_message("Disconnected")
        
    def load_session_state(self):
        if os.path.exists(self.SESSION_FILE):
            try:
                with open(self.SESSION_FILE, 'r') as f:
                    state = json.load(f)
                    self.seq = state.get('outgoing_seq', 0)
                    self.expected_seq = state.get('incoming_seq', 1)
                    self.log_message(f"Loaded session state: outgoing={self.seq}, incoming={self.expected_seq}")
            except Exception as e:
                self.log_message(f"Error loading session state: {e}")
                
    def save_session_state(self):
        try:
            state = {
                'outgoing_seq': self.seq,
                'incoming_seq': self.expected_seq,
                'sender_comp_id': self.SENDERCOMPID,
                'target_comp_id': self.TARGETCOMPID
            }
            with open(self.SESSION_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.log_message(f"Error saving session state: {e}")
            
    def increment_seq(self):
        self.seq += 1
        self.save_session_state()
        return self.seq
        
    def send_logon(self):
        logon_message = simplefix.FixMessage()
        logon_message.append_pair(8, self.FIX_VERSION)
        logon_message.append_pair(35, "A")
        logon_message.append_pair(49, self.SENDERCOMPID)
        logon_message.append_pair(56, self.TARGETCOMPID)
        logon_message.append_pair(34, self.increment_seq())
        logon_message.append_utc_timestamp(52, precision=0)
        logon_message.append_pair(98, "0")
        logon_message.append_pair(108, self.HEARTBEAT)
        
        encoded_msg = logon_message.encode()
        
        # Debug: Log the raw encoded message
        self.log_message(f"Raw encoded logon: {encoded_msg}")
        
        self.sock.sendall(encoded_msg)
        
        # Log the formatted outgoing message
        formatted_msg = self.format_outgoing_message(logon_message)
        self.log_message(f"Sent Logon: {formatted_msg}")
        
        # Debug: Check if checksum is in the message
        if logon_message.get(10):
            self.log_message(f"Checksum found: {logon_message.get(10)}")
        else:
            self.log_message("WARNING: No checksum (tag 10) found in message!")
        
    def send_logout(self):
        logout_message = simplefix.FixMessage()
        self.construct_message("5", logout_message)
        logout_message.remove("60")
        
        encoded_msg = logout_message.encode()
        self.sock.sendall(encoded_msg)
        
        # Log the formatted outgoing message
        formatted_msg = self.format_outgoing_message(logout_message)
        self.log_message(f"Sent Logout: {formatted_msg}")
        self.disconnect()
        
    def construct_message(self, msg_type, message):
        current_seq = self.increment_seq()
        message.append_pair(8, self.FIX_VERSION, header=True)
        message.append_pair(35, msg_type, header=True)
        message.append_pair(49, self.SENDERCOMPID, header=True)
        message.append_pair(56, self.TARGETCOMPID, header=True)
        message.append_pair(34, current_seq, header=True)
        message.append_utc_timestamp(52, precision=0, header=True)
        message.append_utc_timestamp(60, precision=0)
        
        # Store message for potential resend
        if msg_type not in ['0', '1', '2', '4', '5']:
            self.sent_messages[current_seq] = message
            
    def send_raw_fix(self, raw_fix):
        try:
            pairs = raw_fix.split("|")
            fix_message = simplefix.FixMessage()
            msg_type = None
            
            for pair in pairs:
                if '=' in pair:
                    tag, value = pair.split('=', 1)
                    if tag == "35":
                        msg_type = value
                    if tag:
                        fix_message.append_pair(tag, value)
                        
            if msg_type:
                # Remove existing header tags
                for tag in ["8", "35", "49", "56", "34", "52", "60"]:
                    fix_message.remove(tag)
                    
                self.construct_message(msg_type, fix_message)
                encoded_msg = fix_message.encode()
                self.sock.sendall(encoded_msg)
                
                # Log the formatted outgoing message
                formatted_msg = self.format_outgoing_message(fix_message)
                self.log_message(f"Sent Raw FIX: {formatted_msg}")
            else:
                self.log_message("Error: No message type (35) found in raw FIX")
        except Exception as e:
            self.log_message(f"Error sending raw FIX: {e}")
            
    def send_custom_message(self, custom_msg):
        try:
            pairs = custom_msg.split()
            fix_message = simplefix.FixMessage()
            msg_type = None
            
            for pair in pairs:
                if '=' in pair:
                    tag, value = pair.split('=', 1)
                    if tag == "35":
                        msg_type = value
                    fix_message.append_pair(tag, value)
                    
            if msg_type:
                self.construct_message(msg_type, fix_message)
                
                # Fix BodyLength calculation issue
                temp_encoded = fix_message.encode()
                
                # Recalculate correct BodyLength
                checksum_pos = temp_encoded.find(b'\x0110=')
                body_start_pos = temp_encoded.find(b'\x01', temp_encoded.find(b'9=')) + 1
                actual_body_length = checksum_pos - body_start_pos
                
                # Rebuild message with correct BodyLength
                fix_message.remove(9)  # Remove incorrect BodyLength
                fix_message.append_pair(9, str(actual_body_length), header=True)  # Add correct one
                
                encoded_msg = fix_message.encode()
                self.sock.sendall(encoded_msg)
                
                # Log the actual sent message with checksum
                self.log_message(f"Raw sent bytes: {encoded_msg}")
                
                # Log the formatted outgoing message
                formatted_msg = self.format_outgoing_message(fix_message)
                msg_type_desc = self.get_message_type_description(msg_type)
                self.log_message(f"Sent {msg_type_desc}: {formatted_msg}")
                
                # Debug: Check BodyLength calculation
                if b'\x019=' in encoded_msg:
                    body_start = encoded_msg.find(b'\x019=') + 1
                    body_len_end = encoded_msg.find(b'\x01', body_start)
                    body_len_field = encoded_msg[body_start:body_len_end]
                    self.log_message(f"BodyLength field: {body_len_field.decode()}")
                    
                    # Calculate actual body length
                    checksum_start = encoded_msg.find(b'\x0110=')
                    if checksum_start > 0:
                        actual_body = encoded_msg[body_len_end+1:checksum_start]
                        actual_length = len(actual_body)
                        self.log_message(f"Actual body length: {actual_length}")
                        
                        declared_length = int(body_len_field.decode().split('=')[1])
                        if declared_length != actual_length:
                            self.log_message(f"ERROR: BodyLength mismatch! Declared={declared_length}, Actual={actual_length}")
                
                # Also log if checksum was added
                if b'\x0110=' in encoded_msg:
                    checksum_pos = encoded_msg.find(b'\x0110=')
                    checksum_part = encoded_msg[checksum_pos:checksum_pos+7]
                    self.log_message(f"Checksum added: {checksum_part}")
                else:
                    self.log_message("WARNING: No checksum found in encoded message")
            else:
                self.log_message("Error: No message type (35) found")
        except Exception as e:
            self.log_message(f"Error sending custom message: {e}")
            
    def send_orders_from_file(self, filename='fix_orders.txt'):
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
                
            header = lines[0].strip().split('|')
            self.log_message(f"Processing {len(lines) - 1} orders from {filename}")
            
            for i, line in enumerate(lines[1:], 1):
                if not line.strip():
                    continue
                    
                values = line.strip().split('|')
                fix_message = simplefix.FixMessage()
                
                # Add standard order fields
                fix_message.append_pair(35, "D")
                fix_message.append_pair(11, self.generate_clordid())
                fix_message.append_pair(21, "1")
                
                # Map file data to FIX tags
                for tag, value in zip(header, values):
                    if value:
                        if tag == '48':
                            fix_message.append_pair(48, value)
                            fix_message.append_pair(55, value)
                        else:
                            fix_message.append_pair(tag, value)
                            
                self.construct_message("D", fix_message)
                encoded_msg = fix_message.encode()
                self.sock.sendall(encoded_msg)
                
                # Log the formatted outgoing message
                formatted_msg = self.format_outgoing_message(fix_message)
                clord_id = fix_message.get(11).decode() if fix_message.get(11) else 'Unknown'
                self.log_message(f"Sent NewOrderSingle #{i} (ClOrdID={clord_id}): {formatted_msg}")
                time.sleep(0.1)
                
            self.log_message(f"Completed sending {len(lines) - 1} orders")
        except Exception as e:
            self.log_message(f"Error processing orders file: {e}")
            
    def generate_clordid(self):
        self.order_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}{self.order_counter:04d}"
        
    def send_sequence_reset(self, new_seq):
        try:
            reset_msg = simplefix.FixMessage()
            reset_msg.append_pair(8, self.FIX_VERSION)
            reset_msg.append_pair(35, "4")
            reset_msg.append_pair(49, self.SENDERCOMPID)
            reset_msg.append_pair(56, self.TARGETCOMPID)
            reset_msg.append_pair(34, self.increment_seq())
            reset_msg.append_utc_timestamp(52, precision=0)
            reset_msg.append_pair(123, "N")
            reset_msg.append_pair(36, str(new_seq))
            encoded_msg = reset_msg.encode()
            self.sock.sendall(encoded_msg)
            self.seq = new_seq - 1
            self.save_session_state()
            
            # Log the formatted outgoing message
            formatted_msg = self.format_outgoing_message(reset_msg)
            self.log_message(f"Sent SequenceReset: {formatted_msg}")
        except Exception as e:
            self.log_message(f"Error sending sequence reset: {e}")
            
    def send_resend_request(self, begin_seq, end_seq):
        try:
            resend_msg = simplefix.FixMessage()
            resend_msg.append_pair(8, self.FIX_VERSION)
            resend_msg.append_pair(35, "2")
            resend_msg.append_pair(49, self.SENDERCOMPID)
            resend_msg.append_pair(56, self.TARGETCOMPID)
            resend_msg.append_pair(34, self.increment_seq())
            resend_msg.append_utc_timestamp(52, precision=0)
            resend_msg.append_pair(7, str(begin_seq))
            resend_msg.append_pair(16, str(end_seq))
            encoded_msg = resend_msg.encode()
            self.sock.sendall(encoded_msg)
            
            # Log the formatted outgoing message
            formatted_msg = self.format_outgoing_message(resend_msg)
            self.log_message(f"Sent ResendRequest: {formatted_msg}")
        except Exception as e:
            self.log_message(f"Error sending resend request: {e}")
            
    def receive_messages(self):
        parser = simplefix.FixParser()
        parser.set_allow_empty_values(True)
        
        while self.running:
            try:
                response = self.sock.recv(4096)
                if not response:
                    self.log_message("Socket disconnected - exiting program")
                    import sys
                    sys.exit(1)
                    
                response = response.replace(b'|', b'\x01')
                parser.append_buffer(response.decode())
                
                # Process ALL messages in buffer immediately
                while True:
                    message = parser.get_message()
                    if not message:
                        break
                        
                    msg_type = message.get(35)
                    if not msg_type:
                        continue
                    
                    # Handle sequence numbers (skip heartbeats)
                    if msg_type != b'0':
                        msg_seq = int(message.get(34).decode()) if message.get(34) else 0
                        poss_dup_flag = message.get(43) == b'Y'
                        
                        if msg_type == b'2':  # ResendRequest - update inseq to tag34 value
                            self.expected_seq = msg_seq + 1
                            self.save_session_state()
                        elif not poss_dup_flag:  # Normal message - update sequence
                            self.expected_seq = msg_seq + 1
                        # Messages with 43=Y are ignored for sequence update
                        
                    if msg_type == b'0':  # Heartbeat
                        formatted_msg = self.format_fix_message(message)
                        self.log_message(f"Received Heartbeat: {formatted_msg}")
                        self.send_heartbeat()
                    elif msg_type == b'2':  # Resend Request
                        formatted_msg = self.format_fix_message(message)
                        self.log_message(f"Received ResendRequest: {formatted_msg}")
                        self.handle_resend_request(message)
                    elif msg_type == b'4':  # Sequence Reset
                        formatted_msg = self.format_fix_message(message)
                        self.log_message(f"Received SequenceReset: {formatted_msg}")
                        self.handle_sequence_reset(message)
                    elif msg_type == b'5':  # Logout
                        formatted_msg = self.format_fix_message(message)
                        self.log_message(f"Received Logout: {formatted_msg}")
                        self.disconnect()
                        break
                    elif msg_type == b'A':  # Logon
                        formatted_msg = self.format_fix_message(message)
                        self.log_message(f"Received Logon: {formatted_msg}")
                        self.log_message("Session is up!")
                    elif msg_type == b'8':  # ExecRpt:
                        exec_msg = self.format_fix_message(message)
                        self.log_message(f"ExecRpt: {exec_msg}")
                        # Send execution report directly to GUI for processing
                        if hasattr(self, 'gui_callback') and self.gui_callback:
                            self.gui_callback(exec_msg)
                    else:  # Other msg:
                        other_msg = self.format_fix_message(message)
                        msg_type_str = msg_type.decode() if isinstance(msg_type, bytes) else str(msg_type)
                        msg_desc = self.get_message_type_description(msg_type_str)
                        self.log_message(f"Received {msg_desc}: {other_msg}")

            except Exception as e:
                if self.running:
                    self.log_message(f"Socket error: {e} - exiting program")
                    import sys
                    sys.exit(1)
                break
                
    def send_heartbeat(self):
        heartbeat_message = simplefix.FixMessage()
        heartbeat_message.append_pair(8, self.FIX_VERSION)
        heartbeat_message.append_pair(35, "0")
        heartbeat_message.append_pair(49, self.SENDERCOMPID)
        heartbeat_message.append_pair(56, self.TARGETCOMPID)
        heartbeat_message.append_pair(34, self.increment_seq())
        heartbeat_message.append_utc_timestamp(52, precision=0)
        
        encoded_msg = heartbeat_message.encode()
        self.sock.sendall(encoded_msg)
        
        # Log the formatted outgoing message
        formatted_msg = self.format_outgoing_message(heartbeat_message)
        self.log_message(f"Sent Heartbeat: {formatted_msg}")
        
    def handle_resend_request(self, message):
        begin_seq = int(message.get(7).decode())
        end_seq_raw = message.get(16).decode()
        end_seq = 999999 if end_seq_raw == '0' else int(end_seq_raw)
        
        self.log_message(f"Received resend request for seq {begin_seq} to {end_seq}")
        
        # Send single gap fill for entire range
        actual_end_seq = min(end_seq, self.seq)
        self.send_gap_fill(begin_seq, actual_end_seq + 1)
        
    def send_gap_fill(self, begin_seq, new_seq):
        gap_fill_msg = simplefix.FixMessage()
        gap_fill_msg.append_pair(8, self.FIX_VERSION)
        gap_fill_msg.append_pair(35, "4")
        gap_fill_msg.append_pair(49, self.SENDERCOMPID)
        gap_fill_msg.append_pair(56, self.TARGETCOMPID)
        gap_fill_msg.append_pair(34, begin_seq)
        gap_fill_msg.append_utc_timestamp(52, precision=0)
        gap_fill_msg.append_pair(123, "Y")
        gap_fill_msg.append_pair(36, str(new_seq))
        gap_fill_msg.append_pair(43, "Y")
        encoded_msg = gap_fill_msg.encode()
        self.sock.sendall(encoded_msg)
        
        # Log the formatted outgoing message
        formatted_msg = self.format_outgoing_message(gap_fill_msg)
        self.log_message(f"Sent GapFill: {formatted_msg}")
        
    def handle_sequence_reset(self, message):
        new_seq = int(message.get(36).decode())
        gap_fill = message.get(123) == b'Y'
        
        if gap_fill:
            self.log_message(f"Received gap fill reset to seq {new_seq}")
        else:
            self.log_message(f"Received sequence reset to seq {new_seq}")
            
        self.expected_seq = new_seq
        self.save_session_state()
        
    def format_fix_message(self, message):
        """Format FIX message for parsing by GUI"""
        try:
            formatted_pairs = []
            # Get ALL tags from the message, not just a subset
            for tag_num in range(1, 10000):  # Check all possible tags
                value = message.get(tag_num)
                if value:
                    formatted_pairs.append(f"{tag_num}={value.decode() if isinstance(value, bytes) else value}")
            return "|".join(formatted_pairs)
        except Exception as e:
            return str(message)
    
    def format_outgoing_message(self, message):
        """Format outgoing FIX message for logging"""
        try:
            formatted_pairs = []
            # Get ALL tags from the message
            for tag_num in range(1, 10000):
                value = message.get(tag_num)
                if value:
                    formatted_pairs.append(f"{tag_num}={value.decode() if isinstance(value, bytes) else value}")
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