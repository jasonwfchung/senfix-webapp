#!/usr/bin/env python3

import argparse
import json
import sys
import time
from datetime import datetime
from multi_fix_client import MultiFixClient
from quickfix_client import QuickFixClient

class SendFixCLI:
    def __init__(self):
        self.multi_client = None
        self.message_log = []
        
    def log_message(self, message):
        """Log messages to console and internal log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.message_log.append(log_entry)
        
    def session_callback(self, state, session_id):
        """Handle session state changes"""
        self.log_message(f"Session {session_id} -> {state}")
        
    def get_session_name_from_id(self, client, session_id):
        """Convert session_id format to session name"""
        for config in client.session_configs:
            config_session_id = f"{config['fix_version']}:{config['sender_comp_id']}->{config['target_comp_id']}"
            if config_session_id == session_id:
                return config['name']
        # If not found by ID, maybe it's already a name
        for config in client.session_configs:
            if config['name'] == session_id:
                return config['name']
        return None
        
    def init_client(self):
        """Initialize multi-client with proper config loading"""
        if not self.multi_client:
            self.multi_client = MultiFixClient(
                message_callback=self.log_message,
                session_callback=self.session_callback
            )
            # Configuration is loaded automatically in __init__
            self.log_message(f"*** CLI: Loaded {len(self.multi_client.session_configs)} session configs ***")
        return self.multi_client
        
    def login_session(self, session_id, reset_seq=False, wait_timeout=30):
        """
        Login to a specific session with optional sequence reset
        
        Args:
            session_id: FIX session ID (e.g., "FIX.4.2:SENDER->TARGET")
            reset_seq: If True, adds ResetSeqNumFlag=Y to logon
            wait_timeout: Seconds to wait for logon confirmation
        """
        self.log_message(f"*** CLI LOGIN: Attempting to login to {session_id} ***")
        
        client = self.init_client()
        
        # Find session config by session_id format or session name
        session_config = None
        session_name = None
        
        # Try to match by session_id format first
        for config in client.session_configs:
            config_session_id = f"{config['fix_version']}:{config['sender_comp_id']}->{config['target_comp_id']}"
            if config_session_id == session_id:
                session_config = config
                session_name = config['name']
                break
                
        # If not found, try to match by session name
        if not session_config:
            for config in client.session_configs:
                if config['name'] == session_id:
                    session_config = config
                    session_name = config['name']
                    break
                
        if not session_config:
            self.log_message(f"*** CLI ERROR: Session {session_id} not found in configuration ***")
            self.log_message(f"*** Available sessions: ***")
            for config in client.session_configs:
                config_id = f"{config['fix_version']}:{config['sender_comp_id']}->{config['target_comp_id']}"
                self.log_message(f"  {config_id} ({config['name']})")
            return False
            
        self.log_message(f"*** CLI: Found session config: {session_name} ***")
        
        # Check if already logged on (use session name for lookup)
        if session_name in client.sessions:
            session_client = client.sessions[session_name]
            if session_client.is_connected():
                self.log_message(f"*** CLI LOGIN: Session {session_id} already logged on, skipping ***")
                return True
                
        # Set reset sequence flag if requested
        if reset_seq:
            self.log_message(f"*** CLI LOGIN: Setting ResetSeqNumFlag=Y for {session_id} ***")
            # Create client with reset flag override
            if session_id not in client.sessions:
                session_client = QuickFixClient(
                    message_callback=self.log_message,
                    session_callback=self.session_callback
                )
                # Set override for reset sequence flag
                session_client.quickfix_overrides = {"ResetSeqNumFlag": "Y"}
                client.sessions[session_id] = session_client
            else:
                client.sessions[session_id].quickfix_overrides = {"ResetSeqNumFlag": "Y"}
        
        # Connect to session using session name
        success, message = client.connect_session(session_name)
        
        if not success:
            self.log_message(f"*** CLI LOGIN: Failed to connect - {message} ***")
            return False
            
        # Wait for logon confirmation
        self.log_message(f"*** CLI LOGIN: Waiting up to {wait_timeout}s for logon confirmation ***")
        start_time = time.time()
        
        while time.time() - start_time < wait_timeout:
            if session_name in client.sessions:
                session_client = client.sessions[session_name]
                if session_client.is_connected():
                    self.log_message(f"*** CLI LOGIN: Successfully logged on to {session_id} ***")
                    return True
            time.sleep(0.5)
            
        self.log_message(f"*** CLI LOGIN: Timeout waiting for logon to {session_id} ***")
        return False
        
    def send_order(self, session_id, symbol, side, quantity, order_type, price=None, **kwargs):
        """Send FIX NewOrderSingle order"""
        self.log_message(f"*** CLI ORDER: Sending {side} {quantity} {symbol} @ {price or 'MKT'} ***")
        
        client = self.init_client()
        
        session_name = self.get_session_name_from_id(client, session_id)
        if not session_name or session_name not in client.sessions:
            self.log_message(f"*** CLI ERROR: Session {session_id} not found ***")
            return False
            
        session_client = client.sessions[session_name]
        if not session_client.is_connected():
            self.log_message(f"*** CLI ERROR: Session {session_id} not connected ***")
            return False
            
        try:
            order_data = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'order_type': order_type
            }
            
            if price:
                order_data['price'] = price
                
            for key, value in kwargs.items():
                order_data[key] = value
                
            success, clordid = session_client.send_new_order_single(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price
            )
            if success:
                self.log_message(f"*** CLI ORDER: Successfully sent (ClOrdID: {clordid}) ***")
            else:
                self.log_message(f"*** CLI ORDER: Failed to send ***")
            return success
        except Exception as e:
            self.log_message(f"*** CLI ERROR: Failed to send order - {e} ***")
            return False
            
    def send_bulk_orders(self, session_id, filename):
        """Send bulk orders from file"""
        self.log_message(f"*** CLI BULK ORDERS: Processing {filename} for {session_id} ***")
        
        client = self.init_client()
        
        session_name = self.get_session_name_from_id(client, session_id)
        if not session_name or session_name not in client.sessions:
            self.log_message(f"*** CLI ERROR: Session {session_id} not found ***")
            return False
            
        session_client = client.sessions[session_name]
        if not session_client.is_connected():
            self.log_message(f"*** CLI ERROR: Session {session_id} not connected ***")
            return False
            
        try:
            session_client.send_orders_from_file(filename)
            self.log_message(f"*** CLI BULK ORDERS: Completed processing {filename} ***")
            return True
        except Exception as e:
            self.log_message(f"*** CLI ERROR: Failed to process bulk orders - {e} ***")
            return False
            
    def send_raw_fix(self, session_id, raw_fix):
        """Send raw FIX message"""
        self.log_message(f"*** CLI RAW FIX: Sending to {session_id} ***")
        
        client = self.init_client()
        
        session_name = self.get_session_name_from_id(client, session_id)
        if not session_name or session_name not in client.sessions:
            self.log_message(f"*** CLI ERROR: Session {session_id} not found ***")
            return False
            
        session_client = client.sessions[session_name]
        if not session_client.is_connected():
            self.log_message(f"*** CLI ERROR: Session {session_id} not connected ***")
            return False
            
        try:
            success = session_client.send_raw_fix(raw_fix)
            if success:
                self.log_message(f"*** CLI RAW FIX: Successfully sent ***")
            else:
                self.log_message(f"*** CLI RAW FIX: Failed to send ***")
            return success
        except Exception as e:
            self.log_message(f"*** CLI ERROR: Failed to send raw FIX - {e} ***")
            return False
        
    def list_sessions(self):
        """List all available sessions"""
        client = self.init_client()
        
        self.log_message("*** CLI SESSIONS: Available sessions ***")
        for config in client.session_configs:
            session_id = f"{config['fix_version']}:{config['sender_comp_id']}->{config['target_comp_id']}"
            connected = client.is_session_connected(config['name'])
            status = "CONNECTED" if connected else "DISCONNECTED"
            self.log_message(f"  {session_id} ({config['name']}) - {status}")
            
    def disconnect_session(self, session_id):
        """Disconnect from session"""
        client = self.init_client()
        session_name = self.get_session_name_from_id(client, session_id)
        if session_name:
            client.disconnect_session(session_name)
            self.log_message(f"*** CLI: Disconnected {session_id} ***")
        else:
            self.log_message(f"*** CLI ERROR: Session {session_id} not found ***")
            
    def interactive_shell(self):
        """Interactive shell mode for continuous commands"""
        self.log_message("*** CLI SHELL: Starting interactive mode ***")
        self.log_message("*** Type 'help' for commands, 'exit' to quit ***")
        
        while True:
            try:
                command = input("sendfix> ").strip()
                if not command:
                    continue
                    
                parts = command.split()
                cmd = parts[0].lower()
                
                if cmd == 'exit' or cmd == 'quit':
                    self.log_message("*** CLI SHELL: Exiting ***")
                    break
                elif cmd == 'help':
                    self.show_help()
                elif cmd == 'login':
                    if len(parts) < 2:
                        print("Usage: login <session_id> [--reset-seq]")
                        continue
                    session_id = parts[1]
                    reset_seq = '--reset-seq' in parts
                    self.login_session(session_id, reset_seq)
                elif cmd == 'list':
                    self.list_sessions()
                elif cmd == 'order':
                    if len(parts) < 6:
                        print("Usage: order <session_id> <symbol> <side> <quantity> <type> [price]")
                        continue
                    session_id = parts[1]
                    symbol = parts[2]
                    side = parts[3]
                    quantity = parts[4]
                    order_type = parts[5]
                    price = parts[6] if len(parts) > 6 else None
                    self.send_order(session_id, symbol, side, quantity, order_type, price)
                elif cmd == 'bulk':
                    if len(parts) < 3:
                        print("Usage: bulk <session_id> <filename>")
                        continue
                    self.send_bulk_orders(parts[1], parts[2])
                elif cmd == 'raw':
                    if len(parts) < 3:
                        print("Usage: raw <session_id> <fix_message>")
                        continue
                    session_id = parts[1]
                    message = ' '.join(parts[2:])
                    self.send_raw_fix(session_id, message)
                elif cmd == 'disconnect':
                    if len(parts) < 2:
                        print("Usage: disconnect <session_id>")
                        continue
                    self.disconnect_session(parts[1])
                else:
                    print(f"Unknown command: {cmd}. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                self.log_message("\n*** CLI SHELL: Interrupted, exiting ***")
                break
            except EOFError:
                self.log_message("\n*** CLI SHELL: EOF, exiting ***")
                break
            except Exception as e:
                self.log_message(f"*** CLI ERROR: {e} ***")
                
    def show_help(self):
        """Show available commands"""
        print("\nAvailable commands:")
        print("  login <session_id> [--reset-seq]  - Login to FIX session")
        print("  list                              - List all sessions")
        print("  order <session_id> <symbol> <side> <qty> <type> [price] - Send order")
        print("  bulk <session_id> <filename>      - Send bulk orders from file")
        print("  raw <session_id> <message>        - Send raw FIX message")
        print("  disconnect <session_id>           - Disconnect session")
        print("  help                              - Show this help")
        print("  exit                              - Exit shell")
        print()

def main():
    parser = argparse.ArgumentParser(description='SendFix CLI - Backend FIX Operations')
    
    # Add shell mode option
    parser.add_argument('--shell', action='store_true', help='Start interactive shell mode')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Login command
    login_parser = subparsers.add_parser('login', help='Login to FIX session')
    login_parser.add_argument('session_id', help='Session ID (e.g., FIX.4.2:SENDER->TARGET)')
    login_parser.add_argument('--reset-seq', action='store_true', help='Add ResetSeqNumFlag=Y to logon')
    login_parser.add_argument('--timeout', type=int, default=30, help='Logon timeout in seconds')
    login_parser.add_argument('--shell', action='store_true', help='Enter shell mode after login')
    
    # Send order command
    order_parser = subparsers.add_parser('send-order', help='Send FIX order')
    order_parser.add_argument('session_id', help='Session ID')
    order_parser.add_argument('symbol', help='Trading symbol')
    order_parser.add_argument('side', help='Side (1=Buy, 2=Sell)')
    order_parser.add_argument('quantity', help='Order quantity')
    order_parser.add_argument('order_type', help='Order type (1=Market, 2=Limit)')
    order_parser.add_argument('--price', help='Order price (for limit orders)')
    
    # Bulk orders command
    bulk_parser = subparsers.add_parser('bulk-orders', help='Send bulk orders from file')
    bulk_parser.add_argument('session_id', help='Session ID')
    bulk_parser.add_argument('filename', help='Orders file path')
    
    # Raw FIX command
    raw_parser = subparsers.add_parser('raw-fix', help='Send raw FIX message')
    raw_parser.add_argument('session_id', help='Session ID')
    raw_parser.add_argument('message', help='Raw FIX message (pipe separated)')
    
    # List sessions command
    subparsers.add_parser('list-sessions', help='List all available sessions')
    
    # Disconnect command
    disc_parser = subparsers.add_parser('disconnect', help='Disconnect from session')
    disc_parser.add_argument('session_id', help='Session ID')
    
    args = parser.parse_args()
    
    cli = SendFixCLI()
    
    # Check for shell mode
    if args.shell and not args.command:
        cli.interactive_shell()
        return
        
    if not args.command:
        parser.print_help()
        return
        
    try:
        if args.command == 'login':
            success = cli.login_session(args.session_id, args.reset_seq, args.timeout)
            if success and args.shell:
                cli.interactive_shell()
            sys.exit(0 if success else 1)
            
        elif args.command == 'send-order':
            success = cli.send_order(args.session_id, args.symbol, args.side, 
                                   args.quantity, args.order_type, args.price)
            sys.exit(0 if success else 1)
            
        elif args.command == 'bulk-orders':
            success = cli.send_bulk_orders(args.session_id, args.filename)
            sys.exit(0 if success else 1)
            
        elif args.command == 'raw-fix':
            success = cli.send_raw_fix(args.session_id, args.message)
            sys.exit(0 if success else 1)
            
        elif args.command == 'list-sessions':
            cli.list_sessions()
            
        elif args.command == 'disconnect':
            cli.disconnect_session(args.session_id)
            
    except Exception as e:
        print(f"*** CLI ERROR: {e} ***")
        sys.exit(1)

if __name__ == '__main__':
    main()