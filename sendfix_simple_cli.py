#!/usr/bin/env python3

import requests
import argparse
import sys
import json

class SendFixSimpleCLI:
    def __init__(self, webapp_url="http://localhost:8081"):
        self.webapp_url = webapp_url
        
    def send_bulk_orders(self, session_name, filename):
        """Send bulk orders from file via webapp API"""
        try:
            print(f"Reading file: {filename}")
            with open(filename, 'r') as f:
                orders_data = f.read()
            
            print(f"Sending to: {self.webapp_url}/send_bulk_orders")
            print(f"Session: {session_name}")
            print(f"Data length: {len(orders_data)} characters")
                
            response = requests.post(f"{self.webapp_url}/send_bulk_orders", 
                                   json={
                                       'session_name': session_name,
                                       'orders_data': orders_data
                                   })
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Bulk orders sent successfully: {result.get('message', 'OK')}")
                return True
            else:
                print(f"✗ Failed to send bulk orders: {response.text}")
                return False
                
        except FileNotFoundError:
            print(f"✗ File not found: {filename}")
            return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
            
    def send_raw_fix(self, session_name, raw_fix_message):
        """Send raw FIX message via webapp API"""
        try:
            response = requests.post(f"{self.webapp_url}/send_raw_fix", 
                                   json={
                                       'session_name': session_name,
                                       'raw_fix': raw_fix_message
                                   })
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Raw FIX message sent successfully: {result.get('message', 'OK')}")
                return True
            else:
                print(f"✗ Failed to send raw FIX: {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
            
    def login_session(self, session_name):
        """Login to FIX session via webapp API"""
        try:
            # Check if session is already logged on
            print(f"Checking session status: {session_name}")
            response = requests.get(f"{self.webapp_url}/get_sessions")
            
            if response.status_code == 200:
                sessions = response.json()
                for session in sessions:
                    if session['name'] == session_name and session.get('connected', False):
                        print(f"✓ Session {session_name} is already logged on")
                        return True
            
            print(f"Logging into session: {session_name}")
            print(f"Sending to: {self.webapp_url}/login_session")
            
            response = requests.post(f"{self.webapp_url}/login_session", 
                                   json={'session_name': session_name})
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✓ Successfully logged into session: {session_name}")
                    print(f"Message: {result.get('message', 'Connected')}")
                else:
                    print(f"✗ Login failed: {result.get('message', 'Unknown error')}")
                return result.get('success', False)
            else:
                print(f"✗ Failed to login: {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
            
    def list_sessions(self):
        """List available sessions from webapp"""
        try:
            print(f"Connecting to: {self.webapp_url}/get_sessions")
            response = requests.get(f"{self.webapp_url}/get_sessions")
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                sessions = response.json()
                print("Available sessions:")
                for session in sessions:
                    status = "CONNECTED" if session.get('connected', False) else "DISCONNECTED"
                    print(f"  {session['name']} - {status}")
                return True
            else:
                print(f"✗ Failed to get sessions: {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='SendFix Simple CLI - Uses webapp sessions')
    parser.add_argument('--url', default='http://localhost:8081', help='Webapp URL')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Bulk orders command
    bulk_parser = subparsers.add_parser('bulk', help='Send bulk orders from file')
    bulk_parser.add_argument('session_name', help='Session name from webapp')
    bulk_parser.add_argument('filename', help='Orders file path')
    
    # Raw FIX command
    raw_parser = subparsers.add_parser('raw', help='Send raw FIX message')
    raw_parser.add_argument('session_name', help='Session name from webapp')
    raw_parser.add_argument('message', help='Raw FIX message (pipe separated)')
    
    # Login command
    login_parser = subparsers.add_parser('login', help='Login to FIX session')
    login_parser.add_argument('session_name', help='Session name to login to')
    
    # List sessions command
    subparsers.add_parser('list', help='List available sessions')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    cli = SendFixSimpleCLI(args.url)
    
    try:
        if args.command == 'bulk':
            success = cli.send_bulk_orders(args.session_name, args.filename)
            sys.exit(0 if success else 1)
            
        elif args.command == 'raw':
            success = cli.send_raw_fix(args.session_name, args.message)
            sys.exit(0 if success else 1)
            
        elif args.command == 'login':
            success = cli.login_session(args.session_name)
            sys.exit(0 if success else 1)
            
        elif args.command == 'list':
            cli.list_sessions()
            
    except Exception as e:
        print(f"✗ CLI Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()