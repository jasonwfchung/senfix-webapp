#!/usr/bin/env python3

import quickfix as fix
import time
import threading
import signal
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
        
    def connect(self, config_file):
        """Connect using QuickFIX config file"""
        try:
            settings = fix.SessionSettings(config_file)
            store_factory = fix.FileStoreFactory(settings)
            log_factory = fix.FileLogFactory(settings)
            
            self.initiator = fix.SocketInitiator(self, store_factory, settings, log_factory)
            self.initiator.start()
            self.running = True
            self.log("Initiator started")
            return True
        except Exception as e:
            self.log(f"Connect failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from FIX session"""
        try:
            if hasattr(self, 'initiator') and self.running:
                self.initiator.stop()
                self.running = False
                self.logged_on = False
                self.session_id = None
                self.log("Disconnected")
        except Exception as e:
            self.log(f"Disconnect error: {e}")
            
    def send_raw_message(self, raw_fix_msg, sender_comp_id, target_comp_id):
        """Send raw FIX message with overridden comp IDs"""
        if not self.logged_on or not self.session_id:
            self.log("ERROR: Not logged on")
            return False
            
        try:
            # Convert pipe-separated to SOH-separated
            soh_msg = raw_fix_msg.replace('|', '\x01')
            
            # Parse the raw message
            message = fix.Message(soh_msg)
            
            # Override sender and target comp IDs in header
            header = message.getHeader()
            header.setField(fix.SenderCompID(sender_comp_id))
            header.setField(fix.TargetCompID(target_comp_id))
            
            # Send the message
            result = fix.Session.sendToTarget(message, self.session_id)
            self.log(f"Send result: {result}")
            self.log(f"Sent: {message.toString()}")
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
        msg_type_field = fix.MsgType()
        message.getHeader().getField(msg_type_field)
        msg_type = msg_type_field.getValue()
        self.log(f"ADMIN OUT ({msg_type}): {message.toString()}")
        
    def fromAdmin(self, message, sessionID):
        msg_type_field = fix.MsgType()
        message.getHeader().getField(msg_type_field)
        msg_type = msg_type_field.getValue()
        self.log(f"ADMIN IN ({msg_type}): {message.toString()}")
        
    def toApp(self, message, sessionID):
        self.log(f"APP OUT: {message.toString()}")
        
    def fromApp(self, message, sessionID):
        self.log(f"APP IN: {message.toString()}")

def main():
    client = SimpleFIXClient()
    
    print("Simple FIX Test Client")
    print("Commands: connect, disconnect, send, status, quit")
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "quit":
                client.disconnect()
                break
                
            elif cmd == "connect":
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
                    
                raw_msg = input("Raw FIX message: ").strip()
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
                
        except KeyboardInterrupt:
            client.disconnect()
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()