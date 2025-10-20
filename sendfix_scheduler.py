#!/usr/bin/env python3

import json
import time
import schedule
import subprocess
import logging
from datetime import datetime
from pathlib import Path

class SendFixScheduler:
    def __init__(self, config_file='scheduler_config.json'):
        self.config_file = config_file
        self.setup_logging()
        self.load_config()
        
    def setup_logging(self):
        """Setup logging for scheduler"""
        logging.basicConfig(
            filename='sendfix_scheduler.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        """Load scheduler configuration"""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            self.logger.info(f"Loaded scheduler config from {self.config_file}")
        except FileNotFoundError:
            # Create default config
            self.config = {
                "jobs": [
                    {
                        "name": "morning_bulk_orders",
                        "schedule": "09:00",
                        "command": "bulk-orders",
                        "session_id": "FIX.4.2:SENDER->TARGET",
                        "filename": "morning_orders.txt",
                        "enabled": False
                    }
                ]
            }
            self.save_config()
            
    def save_config(self):
        """Save scheduler configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
            
    def execute_cli_command(self, command_args):
        """Execute SendFix CLI command"""
        try:
            cmd = ['python3', 'sendfix_cli.py'] + command_args
            self.logger.info(f"Executing: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"Command succeeded: {result.stdout}")
                return True
            else:
                self.logger.error(f"Command failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Command timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            return False
            
    def job_bulk_orders(self, session_id, filename):
        """Scheduled job: Send bulk orders"""
        self.logger.info(f"Starting bulk orders job: {session_id} -> {filename}")
        
        # Check if file exists
        if not Path(filename).exists():
            self.logger.error(f"Orders file not found: {filename}")
            return False
            
        # Execute bulk orders command
        return self.execute_cli_command(['bulk-orders', session_id, filename])
        
    def job_login_session(self, session_id, reset_seq=False):
        """Scheduled job: Login to session"""
        self.logger.info(f"Starting login job: {session_id}")
        
        cmd_args = ['login', session_id]
        if reset_seq:
            cmd_args.append('--reset-seq')
            
        return self.execute_cli_command(cmd_args)
        
    def job_heartbeat(self, session_id):
        """Scheduled job: Send heartbeat"""
        self.logger.info(f"Starting heartbeat job: {session_id}")
        return self.execute_cli_command(['heartbeat', session_id])
        
    def job_raw_fix(self, session_id, message):
        """Scheduled job: Send raw FIX message"""
        self.logger.info(f"Starting raw FIX job: {session_id}")
        return self.execute_cli_command(['raw-fix', session_id, message])
        
    def schedule_jobs(self):
        """Schedule all jobs from config"""
        for job in self.config['jobs']:
            if not job.get('enabled', False):
                continue
                
            job_name = job['name']
            schedule_time = job['schedule']
            command = job['command']
            
            self.logger.info(f"Scheduling job: {job_name} at {schedule_time}")
            
            if command == 'bulk-orders':
                schedule.every().day.at(schedule_time).do(
                    self.job_bulk_orders,
                    job['session_id'],
                    job['filename']
                ).tag(job_name)
                
            elif command == 'login':
                schedule.every().day.at(schedule_time).do(
                    self.job_login_session,
                    job['session_id'],
                    job.get('reset_seq', False)
                ).tag(job_name)
                
            elif command == 'heartbeat':
                # For heartbeat, schedule_time can be interval like "5m" for every 5 minutes
                if schedule_time.endswith('m'):
                    minutes = int(schedule_time[:-1])
                    schedule.every(minutes).minutes.do(
                        self.job_heartbeat,
                        job['session_id']
                    ).tag(job_name)
                else:
                    schedule.every().day.at(schedule_time).do(
                        self.job_heartbeat,
                        job['session_id']
                    ).tag(job_name)
                    
            elif command == 'raw-fix':
                schedule.every().day.at(schedule_time).do(
                    self.job_raw_fix,
                    job['session_id'],
                    job['message']
                ).tag(job_name)
                
    def run(self):
        """Run the scheduler"""
        self.logger.info("Starting SendFix Scheduler")
        print("SendFix Scheduler started. Press Ctrl+C to stop.")
        
        self.schedule_jobs()
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Scheduler stopped by user")
            print("\nScheduler stopped.")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='SendFix Scheduler - Automated FIX Operations')
    parser.add_argument('--config', default='scheduler_config.json', help='Config file path')
    parser.add_argument('--create-sample', action='store_true', help='Create sample config file')
    
    args = parser.parse_args()
    
    if args.create_sample:
        sample_config = {
            "jobs": [
                {
                    "name": "morning_login",
                    "schedule": "08:30",
                    "command": "login",
                    "session_id": "FIX.4.2:SENDER->TARGET",
                    "reset_seq": True,
                    "enabled": True
                },
                {
                    "name": "morning_bulk_orders",
                    "schedule": "09:00",
                    "command": "bulk-orders",
                    "session_id": "FIX.4.2:SENDER->TARGET",
                    "filename": "morning_orders.txt",
                    "enabled": False
                },
                {
                    "name": "periodic_heartbeat",
                    "schedule": "5m",
                    "command": "heartbeat",
                    "session_id": "FIX.4.2:SENDER->TARGET",
                    "enabled": False
                },
                {
                    "name": "eod_logout",
                    "schedule": "17:30",
                    "command": "raw-fix",
                    "session_id": "FIX.4.2:SENDER->TARGET",
                    "message": "35=5",
                    "enabled": False
                }
            ]
        }
        
        with open('scheduler_config_sample.json', 'w') as f:
            json.dump(sample_config, f, indent=2)
        print("Sample config created: scheduler_config_sample.json")
        return
        
    scheduler = SendFixScheduler(args.config)
    scheduler.run()

if __name__ == '__main__':
    main()