"""Main Personal AI Employee application."""

import time
import threading
from pathlib import Path
from typing import Dict, Any
from .config import Config
from .entities import FileEntity
from .file_monitor import FileMonitor
from .logger import Logger
from .vault_manager import VaultManager
from .state_manager import StateManager
from .claude_integration import ClaudeIntegration
from .document_processor import DocumentProcessor
from .document_classifier import DocumentClassifier
from .task_manager import TaskManager
from .info_retrieval import InformationRetrieval
from .approval_system import ApprovalSystem
from .security import SecurityEnforcer, ConstraintChecker


class AIEmployee:
    """Main Personal AI Employee application."""

    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        self.config = Config(config_path)

        # Initialize logger
        self.logger = Logger(self.config.log_directory)

        # Initialize security enforcer first
        self.security_enforcer = SecurityEnforcer(self.logger, self.config.vault_path)

        # Initialize vault manager
        self.vault_manager = VaultManager(self.config.vault_path, self.logger)

        # Initialize state manager
        self.state_manager = StateManager(self.vault_manager, self.logger)

        # Initialize Claude integration
        self.claude_integration = ClaudeIntegration(self.logger)

        # Initialize document processor
        self.document_processor = DocumentProcessor(
            self.claude_integration,
            self.vault_manager,
            self.state_manager,
            self.logger
        )

        # Initialize document classifier
        self.document_classifier = DocumentClassifier()

        # Initialize task manager
        self.task_manager = TaskManager(self.vault_manager, self.logger)

        # Initialize information retrieval
        self.info_retrieval = InformationRetrieval(self.vault_manager, self.logger)

        # Initialize approval system
        self.approval_system = ApprovalSystem(self.vault_manager, self.logger)

        # Initialize file monitor
        self.file_monitor = FileMonitor(self.config.vault_path)
        self.file_monitor.add_callback(self._handle_file_event)

        # Initialize constraint checker
        self.constraint_checker = ConstraintChecker(self.security_enforcer, self.logger)

        # Track processing threads
        self.processing_threads = {}

        self.logger.info("ai_employee", "initialized",
                        "AI Employee initialized successfully")

    def _handle_file_event(self, file_path: str, event_type: str):
        """Handle file system events."""
        file_path_obj = Path(file_path)

        self.logger.info("ai_employee", "file_detected",
                        f"Detected {event_type} event for {file_path_obj.name}",
                        file_ref=file_path)

        # Only process new files in the inbox folder
        if self.config.input_folder in str(file_path_obj):
            # Start processing in a separate thread to avoid blocking
            processing_thread = threading.Thread(
                target=self._process_new_file,
                args=(file_path_obj,)
            )
            processing_thread.daemon = True
            processing_thread.start()

            # Store the thread reference
            self.processing_threads[file_path_obj.name] = processing_thread

    def _process_new_file(self, file_path: Path):
        """Process a new file from the inbox."""
        try:
            # Update state to processing
            self.state_manager.transition_file(file_path, 'processing')

            # Classify the file
            file_type = self.document_classifier.classify_file(file_path)

            # Check if file is processable
            if not self.document_classifier.is_processable(file_path):
                self.logger.warn("ai_employee", "file_not_processable",
                                f"File {file_path.name} is not processable, moving to rejected",
                                file_ref=str(file_path))

                # Move to rejected folder
                self.state_manager.transition_file(file_path, 'rejected')
                return

            # Get recommended processing type
            processing_type = self.document_classifier.get_processing_recommendation(file_path)

            # Assess complexity to determine if approval is needed
            needs_approval, reason = self.document_processor.assess_complexity(file_path)

            if needs_approval:
                # Create approval request
                self.logger.info("ai_employee", "approval_needed",
                                f"File {file_path.name} needs approval: {reason}",
                                file_ref=str(file_path))

                # Create an operation entity for the approval
                from .entities import OperationEntity
                operation = OperationEntity(
                    type=f"document_{processing_type}",
                    file_id=str(file_path),
                    description=f"Processing {file_path.name} with {processing_type}",
                    requires_approval=True
                )

                # Create approval request
                approval_file = self.document_processor.create_approval_request(file_path, operation)

                if approval_file:
                    # Move original file to pending approval
                    self.state_manager.transition_file(file_path, 'pending_approval')

                    self.logger.info("ai_employee", "approval_requested",
                                    f"Approval requested for {file_path.name}",
                                    file_ref=str(file_path))
                else:
                    # If approval request creation failed, move to error
                    self.state_manager.transition_file(file_path, 'error')
            else:
                # Process the file directly
                self.logger.info("ai_employee", "processing_auto",
                                f"Processing {file_path.name} automatically",
                                file_ref=str(file_path))

                operation = self.document_processor.process_document(file_path, processing_type)

                if operation and operation.status == "completed":
                    # Move to completed
                    self.state_manager.transition_file(file_path, 'completed')

                    self.logger.info("ai_employee", "processing_completed",
                                    f"Auto-processing completed for {file_path.name}",
                                    file_ref=str(file_path))
                else:
                    # Move to error
                    self.state_manager.transition_file(file_path, 'error')

                    self.logger.error("ai_employee", "processing_failed",
                                     f"Auto-processing failed for {file_path.name}",
                                     file_ref=str(file_path))

        except Exception as e:
            self.logger.error("ai_employee", "file_processing_error",
                             f"Error processing file {file_path.name}: {str(e)}")

            # Move to error folder if there's an error
            try:
                self.state_manager.transition_file(file_path, 'error')
            except:
                pass  # If we can't even move to error, log it
            finally:
                self.logger.error("ai_employee", "moved_to_error",
                                 f"File {file_path.name} moved to error folder due to processing error")

    def start_monitoring(self):
        """Start monitoring for file changes."""
        self.file_monitor.start_monitoring()
        self.approval_system.start_monitoring_approvals()

        # Perform initial security check
        self.constraint_checker.verify_bronze_tier_compliance()

        self.logger.info("ai_employee", "monitoring_started",
                        "File monitoring started")

    def stop_monitoring(self):
        """Stop monitoring for file changes."""
        self.approval_system.stop_monitoring_approvals()
        self.file_monitor.stop_monitoring()

        self.logger.info("ai_employee", "monitoring_stopped",
                        "File monitoring stopped")

    def run(self):
        """Run the AI Employee continuously."""
        self.start_monitoring()

        try:
            while True:
                # Periodic security checks
                time.sleep(1)

                # Perform periodic constraint compliance check
                if int(time.time()) % 30 == 0:  # Every 30 seconds
                    self.constraint_checker.verify_bronze_tier_compliance()
        except KeyboardInterrupt:
            self.logger.info("ai_employee", "shutdown_initiated",
                           "Shutdown initiated by user")
        finally:
            self.stop_monitoring()


def main():
    """Main entry point for the AI Employee."""
    ai_employee = AIEmployee()
    ai_employee.run()


if __name__ == "__main__":
    main()