"""Document processing orchestrator."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from .entities import FileEntity, OperationEntity, ApprovalEntity
from .claude_integration import ClaudeIntegration
from .vault_manager import VaultManager
from .state_manager import StateManager
from .logger import Logger


class DocumentProcessor:
    """Orchestrates document processing operations."""

    def __init__(self, claude_integration: ClaudeIntegration,
                 vault_manager: VaultManager,
                 state_manager: StateManager,
                 logger: Logger):
        self.claude_integration = claude_integration
        self.vault_manager = vault_manager
        self.state_manager = state_manager
        self.logger = logger

    def assess_complexity(self, file_path: Path) -> tuple[bool, str]:
        """
        Assess if a document requires human approval based on complexity.

        Returns:
            tuple: (needs_approval: bool, reason: str)
        """
        try:
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Simple heuristic: if file is large (>10000 chars) or contains certain keywords,
            # it might need approval
            needs_approval = len(content) > 10000  # Large files need approval

            # Check for sensitive content that might need approval
            content_lower = content.lower()
            sensitive_keywords = ['confidential', 'private', 'personal', 'financial', 'contract', 'agreement']

            for keyword in sensitive_keywords:
                if keyword in content_lower:
                    needs_approval = True
                    break

            reason = "Large file" if len(content) > 10000 else "Contains sensitive content" if needs_approval else "Simple document"

            self.logger.info("processor", "complexity_assessment",
                            f"Assessed complexity for {file_path.name}: needs_approval={needs_approval}, reason={reason}",
                            file_ref=str(file_path))

            return needs_approval, reason

        except Exception as e:
            self.logger.error("processor", "complexity_assessment_error",
                             f"Error assessing complexity for {file_path}: {str(e)}")
            return True, "Error assessing complexity - defaulting to requiring approval"

    def process_document(self, file_path: Path, processing_type: str = "analyze") -> Optional[OperationEntity]:
        """Process a document using Claude Code."""
        try:
            operation = OperationEntity(
                type=f"document_{processing_type}",
                file_id=str(file_path),
                description=f"Processing document {file_path.name} with {processing_type}",
                status="in_progress"
            )

            self.logger.info("processor", "document_processing_started",
                            f"Starting {processing_type} for {file_path.name}",
                            file_ref=str(file_path),
                            operation_ref=operation.id)

            # Process the document based on the processing type
            result = None
            if processing_type == "summarize":
                result = self.claude_integration.summarize_document(file_path)
            elif processing_type == "categorize":
                result = self.claude_integration.categorize_document(file_path)
            elif processing_type == "analyze":
                result = self.claude_integration.analyze_document(file_path)
            elif processing_type == "transform":
                result = self.claude_integration.transform_document(file_path, "standard")
            else:
                self.logger.error("processor", "invalid_processing_type",
                                 f"Invalid processing type: {processing_type}")
                operation.status = "failed"
                return operation

            if result is not None:
                # Save the result to a new file in the processing folder
                result_filename = f"{file_path.stem}_processed_{processing_type}.txt"

                # Create the processed file
                processed_file = self.vault_manager.create_file(
                    "processing",
                    result_filename,
                    result
                )

                if processed_file:
                    operation.result = str(processed_file)
                    operation.status = "completed"

                    self.logger.info("processor", "document_processing_completed",
                                    f"Completed {processing_type} for {file_path.name}",
                                    file_ref=str(file_path),
                                    operation_ref=operation.id)
                else:
                    operation.status = "failed"
            else:
                operation.status = "failed"

            return operation

        except Exception as e:
            self.logger.error("processor", "document_processing_error",
                             f"Error processing document {file_path}: {str(e)}")

            operation.status = "failed"
            operation.result = str(e)
            return operation

    def create_approval_request(self, file_path: Path, operation: OperationEntity) -> Optional[Path]:
        """Create an approval request file for human review."""
        try:
            # Create approval request data
            approval_data = {
                "request_id": operation.id,
                "timestamp": operation.created_at.isoformat(),
                "request_type": operation.type,
                "description": operation.description,
                "justification": f"The document {file_path.name} requires human review due to complexity.",
                "options": [
                    {
                        "option_id": "approve",
                        "description": "Approve the operation",
                        "expected_outcome": "The operation will proceed as planned"
                    },
                    {
                        "option_id": "reject",
                        "description": "Reject the operation",
                        "expected_outcome": "The operation will be cancelled"
                    },
                    {
                        "option_id": "modify",
                        "description": "Modify the operation",
                        "expected_outcome": "The operation will be adjusted based on your input"
                    }
                ],
                "file_context": str(file_path),
                "risk_level": "medium",
                "urgency": "normal",
                "created_by": "ai-employee"
            }

            # Create the approval request file in the pending-approval folder
            approval_filename = f"approval_request_{operation.id}.json"
            approval_file = self.vault_manager.create_file(
                "pending-approval",
                approval_filename,
                json.dumps(approval_data, indent=2)
            )

            if approval_file:
                self.logger.audit("processor", "approval_request_created",
                                f"Created approval request for {file_path.name}",
                                file_ref=str(approval_file),
                                operation_ref=operation.id)
                return approval_file
            else:
                self.logger.error("processor", "approval_request_failed",
                                 f"Failed to create approval request for {file_path.name}")
                return None

        except Exception as e:
            self.logger.error("processor", "approval_request_error",
                             f"Error creating approval request for {file_path}: {str(e)}")
            return None