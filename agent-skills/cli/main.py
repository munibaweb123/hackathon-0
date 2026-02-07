"""
Main CLI Module

This module serves as the main entry point to coordinate all components of the Silver Tier Agent Skills system.
"""

import argparse
import sys
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to the path so imports work correctly
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add the agent-skills directory to the path for easier imports
agent_skills_path = Path(__file__).parent.parent
sys.path.insert(0, str(agent_skills_path))

from core.vault_interface import VaultInterface
from core.logger import Logger
from watchers.gmail_watcher import GmailWatcher
from watchers.linkedin_watcher import LinkedInWatcher
from skills.reasoning_skill import ReasoningSkill
from skills.planning_skill import PlanningSkill
from skills.execution_skill import ExecutionSkill
from skills.communication_skill import CommunicationSkill
from mcp_server.server import MCPServer
from scheduler.task_scheduler import TaskScheduler


class SilverTierAgent:
    """
    Main class for the Silver Tier Personal AI Employee.
    Coordinates all components of the system.
    """

    def __init__(self):
        """Initialize the Silver Tier Agent with all required components."""
        # Initialize core components
        self.vault_interface = VaultInterface(vault_path=os.getenv('VAULT_PATH', './vault'))
        self.logger = Logger(log_dir=os.getenv('LOG_DIR', './logs'))

        # Initialize watchers
        self.gmail_watcher = GmailWatcher(self.vault_interface, self.logger)
        self.linkedin_watcher = LinkedInWatcher(self.vault_interface, self.logger)

        # Initialize skills
        self.reasoning_skill = ReasoningSkill(self.vault_interface, self.logger)
        self.planning_skill = PlanningSkill(self.vault_interface, self.logger)
        self.execution_skill = ExecutionSkill(
            self.vault_interface, self.logger,
            mcp_server_host=os.getenv('MCP_SERVER_HOST', 'localhost'),
            mcp_server_port=int(os.getenv('MCP_SERVER_PORT', '8000'))
        )
        self.communication_skill = CommunicationSkill(self.vault_interface, self.logger)

        # Initialize MCP server
        self.mcp_server = MCPServer(
            host=os.getenv('MCP_SERVER_HOST', 'localhost'),
            port=int(os.getenv('MCP_SERVER_PORT', '8000')),
            logger=self.logger
        )

        # Initialize scheduler
        self.scheduler = TaskScheduler(self.logger)

        # Store all components for easy access
        self.components = {
            'vault_interface': self.vault_interface,
            'logger': self.logger,
            'gmail_watcher': self.gmail_watcher,
            'linkedin_watcher': self.linkedin_watcher,
            'reasoning_skill': self.reasoning_skill,
            'planning_skill': self.planning_skill,
            'execution_skill': self.execution_skill,
            'communication_skill': self.communication_skill,
            'mcp_server': self.mcp_server,
            'scheduler': self.scheduler
        }

    def start_watchers(self):
        """Start all watcher services."""
        print("Starting watchers...")

        # Schedule watchers to run periodically using the scheduler
        self.scheduler.schedule_task(
            "gmail_polling",
            self.gmail_watcher.run_continuous_monitoring,
            interval_seconds=self.gmail_watcher.check_interval
        )

        self.scheduler.schedule_task(
            "linkedin_polling",
            self.linkedin_watcher.run_continuous_monitoring,
            interval_seconds=self.linkedin_watcher.check_interval
        )

        print("Watchers scheduled.")

    def start_mcp_server(self):
        """Start the MCP server."""
        print("Starting MCP server...")
        # In a real implementation, this would start the server in a separate thread
        # For now, we'll just log that it's initialized
        self.logger.log_system_event(
            event_type="mcp_server_init",
            component="main",
            message="MCP server initialized",
            details={
                "host": self.mcp_server.host,
                "port": self.mcp_server.port
            }
        )
        print(f"MCP server initialized at {self.mcp_server.host}:{self.mcp_server.port}")

    def start_scheduler(self):
        """Start the task scheduler."""
        print("Starting scheduler...")
        self.scheduler.start()
        print("Scheduler started.")

    def start_system(self):
        """Start the complete Silver Tier system."""
        print("Starting Silver Tier Personal AI Employee...")

        # Start the scheduler first
        self.start_scheduler()

        # Start the MCP server
        self.start_mcp_server()

        # Start watchers
        self.start_watchers()

        print("Silver Tier system is running.")

    def stop_system(self):
        """Stop the complete Silver Tier system."""
        print("Stopping Silver Tier Personal AI Employee...")

        # Stop scheduler
        self.scheduler.stop()

        # Stop MCP server
        self.mcp_server.stop()

        # Stop watchers
        self.gmail_watcher.stop_monitoring()
        self.linkedin_watcher.stop_monitoring()

        print("Silver Tier system stopped.")

    def process_watcher_events(self):
        """Manually process any new watcher events."""
        print("Processing watcher events...")

        # Process files from inbox
        inbox_files = self.vault_interface.get_files_in_folder("inbox")

        for file_path in inbox_files:
            if file_path.suffix.lower() == '.json':
                print(f"Processing watcher output: {file_path}")

                # Read the watcher output
                watcher_output_content = self.vault_interface.read_file(file_path)

                # Use reasoning skill to generate a plan
                reasoning_input = {
                    'watcher_output_path': str(file_path),
                    'context': 'Process this watcher output and generate a plan'
                }

                reasoning_result = self.reasoning_skill.execute(reasoning_input)

                if reasoning_result:
                    print(f"Plan generated: {reasoning_result.get('plan_id')}")

                    # Move the processed file to 'processed' folder
                    self.vault_interface.move_file(
                        source_path=file_path,
                        destination_folder="processed"
                    )
                else:
                    print(f"Failed to generate plan for {file_path}")

                    # Move to error folder
                    self.vault_interface.move_file(
                        source_path=file_path,
                        destination_folder="processed",  # Actually should be error folder - this is a simplification
                        new_filename=f"error_{file_path.name}"
                    )

    def run_single_cycle(self):
        """Run a single cycle of the agent workflow."""
        print("Running single cycle...")

        # 1. Poll watchers for new events
        self.gmail_watcher.poll_gmail()
        self.linkedin_watcher.poll_linkedin()

        # 2. Process any new watcher events
        self.process_watcher_events()

        print("Single cycle completed.")

    def get_system_status(self):
        """Get the status of all system components."""
        status = {
            'timestamp': str(datetime.now()),
            'components': {}
        }

        # Check status of each component
        for name, component in self.components.items():
            if hasattr(component, 'get_status'):
                status['components'][name] = component.get_status()
            elif hasattr(component, 'running'):
                status['components'][name] = {'running': component.running}
            elif hasattr(component, 'is_running'):
                status['components'][name] = {'running': component.is_running}
            else:
                status['components'][name] = {'status': 'initialized'}

        return status


def main():
    """Main entry point for the Silver Tier Agent."""
    parser = argparse.ArgumentParser(description="Silver Tier Personal AI Employee")
    parser.add_argument('command', nargs='?', default='start',
                       help='Command to execute (start, stop, status, process, cycle)')
    parser.add_argument('--foreground', action='store_true',
                       help='Run in foreground (don\'t daemonize)')

    args = parser.parse_args()

    # Create the agent
    agent = SilverTierAgent()

    if args.command == 'start':
        print("Starting Silver Tier Agent...")
        agent.start_system()

        if not args.foreground:
            print("Agent started in background. Use 'python main.py stop' to stop.")
            return

        # If running in foreground, keep running
        try:
            print("Agent running. Press Ctrl+C to stop.")
            while True:
                import time
                time.sleep(10)  # Sleep briefly to allow interruption
        except KeyboardInterrupt:
            print("\nReceived interrupt signal. Stopping agent...")
            agent.stop_system()

    elif args.command == 'stop':
        print("Stopping Silver Tier Agent...")
        agent.stop_system()

    elif args.command == 'status':
        status = agent.get_system_status()
        print("System Status:")
        for component, comp_status in status['components'].items():
            print(f"  {component}: {comp_status}")

    elif args.command == 'process':
        print("Processing watcher events...")
        agent.process_watcher_events()

    elif args.command == 'cycle':
        print("Running single cycle...")
        agent.run_single_cycle()

    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()


if __name__ == "__main__":
    main()