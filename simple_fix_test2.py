#!/usr/bin/env python3

import quickfix as fix
import time
import sys

class SimpleFIXClient(fix.Application):
    def __init__(self):
        super().__init__()
        self.session_id = None
        self.logged_on = False
        self.running = False
        self.initiator = None
        
    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")
        sys.stdout.flush()
        
    def connect(self, config_file):
        """Connect using QuickFIX config file"""
        try:
            if self.running:
                self.log("Already running")
                return False
                
            settings = fix.SessionSettings(config_file)
            store_factory = fix.FileStoreFactory(settings)
            log_factory = fix.ScreenLogFactory(settings)  # Use screen log instead of file
            
            self.initiator = fix.SocketInitiator(self, store_factory, settings, log_factory)
            self.initiator.start()
            self.running = True
            self.log("Initiator started")
            
            # Wait a bit for connection
            time.sleep(2)
            return True
            
        except Exception as e:
            self.log(f"Connect failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from FIX session"""
        try:
            if self.initiator and self.running:
                self.log("Stopping initiator...")
                self.initiator.stop()
                self.running = False
                self.logged_on = False
                self.session_id = None
                self.initiator = None
                self.log("Disconnected")
                time.sleep(1)  # Give time to cleanup
        except Exception as e:
            self.log(f"Disconnect error: {e}")
            
    def send_raw_message(self, raw_fix_msg, sender_comp_id, target_comp_id):
        """Send raw FIX message with overridden comp IDs"""
        if not self.logged_on or not self.session_id:
            self.log("ERROR: Not logged on")
            return False
            
        try:
            # Create new message from scratch instead of parsing raw
            message = fix.Message()
            
            # Parse fields from raw message (skip header fields)
            fields = raw_fix_msg.split('|')
            for field in fields:
                if '=' in field:
                    tag, value = field.split('=', 1)
                    tag_num = int(tag)
                    # Skip header fields - let QuickFIX handle them
                    if tag_num not in [8, 9, 35, 49, 56, 34, 52, 10]:
                        message.setField(tag_num, value)
            
            # Set message type if provided
            for field in fields:
                if field.startswith('35='):
                    msg_type = field.split('=')[1]
                    message.getHeader().setField(fix.MsgType(msg_type))
                    break
            
            # Send the message - QuickFIX will add proper header/trailer
            result = fix.Session.sendToTarget(message, self.session_id)
            self.log(f"Send result: {result}")
            return result
            
        except Exception as e:
            self.log(f"Send error: {e}")
            return False
    
    # QuickFIX callbacks
    def onCreate(self, sessionID):
        self.session_id = sessionID
        self.log(f"Session created: {sessionID}")
        
    def onLogon(self, sessionID):
        self.logged_on = True
        self.session_id = sessionID
        self.log(f"LOGGED ON: {sessionID}")
        
    def onLogout(self, sessionID):
        self.logged_on = False
        self.log(f"LOGGED OUT: {sessionID}")
        
    def toAdmin(self, message, sessionID):
        try:
            msg_type_field = fix.MsgType()
            message.getHeader().getField(msg_type_field)
            msg_type = msg_type_field.getValue()
            self.log(f"ADMIN OUT ({msg_type})")
        except:
            self.log("ADMIN OUT")
        
    def fromAdmin(self, message, sessionID):
        try:
            msg_type_field = fix.MsgType()
            message.getHeader().getField(msg_type_field)
            msg_type = msg_type_field.getValue()
            self.log(f"ADMIN IN ({msg_type})")
        except:
            self.log("ADMIN IN")
        
    def toApp(self, message, sessionID):
        self.log("APP OUT")
        
    def fromApp(self, message, sessionID):
        self.log("APP IN")

def main():
    client = SimpleFIXClient()
    
    print("Simple FIX Test Client v2")
    print("Commands: connect, disconnect, send, status, quit")
    
    try:
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd == "quit":
                    client.disconnect()
                    break
                    
                elif cmd == "connect":
                    if client.running:
                        print("Already connected. Disconnect first.")
                        continue
                    config = input("Config file path: ").strip()
                    if client.connect(config):
                        print("Connection initiated...")
                    else:
                        print("Connection failed")
                        
                elif cmd == "disconnect":
                    client.disconnect()
                    print("Disconnected")
                    
                elif cmd == "send":
                    if not client.logged_on:
                        print("ERROR: Not logged on")
                        continue
                        
                    raw_msg = input("Raw FIX fields (tag=value|tag=value): ").strip()
                    sender = input("Sender CompID: ").strip()
                    target = input("Target CompID: ").strip()
                    
                    if client.send_raw_message(raw_msg, sender, target):
                        print("Message sent")
                    else:
                        print("Send failed")
                        
                elif cmd == "status":
                    print(f"Running: {client.running}")
                    print(f"Logged on: {client.logged_on}")
                    print(f"Session ID: {client.session_id}")
                    
                else:
                    print("Unknown command")
                    
            except EOFError:
                break
            except Exception as e:
                print(f"Error: {e}")
                
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        print("\nExiting...")

if __name__ == "__main__":
    main()