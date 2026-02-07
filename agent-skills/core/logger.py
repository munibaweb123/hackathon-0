"""
Logger Module

This module provides methods for human-readable, timestamped, tamper-evident logging.
All operations must be logged with timestamps and reasoning, enabling complete
audit trails for accountability and debugging purposes.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import hashlib


class Logger:
    """
    Logger for human-readable, timestamped, tamper-evident logs.
    Ensures all AI employee activities are fully transparent and auditable.
    """

    def __init__(self, log_dir: str = "./logs"):
        """
        Initialize the logger with the log directory.

        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize log file paths
        self.watcher_log = self.log_dir / "watcher_events.log"
        self.reasoning_log = self.log_dir / "reasoning_outputs.log"
        self.planning_log = self.log_dir / "plan_generation.log"
        self.approval_log = self.log_dir / "approval_decisions.log"
        self.execution_log = self.log_dir / "mcp_executions.log"
        self.system_log = self.log_dir / "system_events.log"
        self.audit_trail_log = self.log_dir / "audit_trail.log"  # Comprehensive audit trail

        # Create log files if they don't exist
        for log_file in [
            self.watcher_log,
            self.reasoning_log,
            self.planning_log,
            self.approval_log,
            self.execution_log,
            self.system_log,
            self.audit_trail_log
        ]:
            log_file.touch(exist_ok=True)

    def _write_log_entry(self, log_file: Path, entry: Dict[str, Any]):
        """
        Write a log entry to the specified log file.

        Args:
            log_file: Path to the log file
            entry: Dictionary containing the log entry
        """
        # Add tamper evidence hash
        entry['hash'] = self._calculate_hash(entry)

        # Write entry as JSON line
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')

    def _write_audit_trail_entry(self, entry: Dict[str, Any]):
        """
        Write an entry to the comprehensive audit trail.

        Args:
            entry: Dictionary containing the audit trail entry
        """
        # Add tamper evidence hash
        entry['hash'] = self._calculate_hash(entry)

        # Write entry as JSON line to the audit trail
        with open(self.audit_trail_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')

    def _calculate_hash(self, entry: Dict[str, Any]) -> str:
        """
        Calculate a hash for tamper evidence.

        Args:
            entry: Log entry to hash

        Returns:
            SHA-256 hash of the entry
        """
        # Remove existing hash if present to avoid recursive hashing
        entry_copy = entry.copy()
        entry_copy.pop('hash', None)

        # Create string representation of the entry
        entry_str = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))

        # Calculate SHA-256 hash
        return hashlib.sha256(entry_str.encode()).hexdigest()

    def log_watcher_event(self, event_type: str, source: str, details: Dict[str, Any]):
        """
        Log a watcher detection event.

        Args:
            event_type: Type of event detected
            source: Source of the event (Gmail, LinkedIn, etc.)
            details: Additional details about the event
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "log_type": "watcher_event",
            "event_type": event_type,
            "source": source,
            "details": details
        }
        self._write_log_entry(self.watcher_log, entry)
        self._write_audit_trail_entry(entry)

    def log_reasoning_output(self, input_context: str, output_plan: str, reasoning_steps: List[str]):
        """
        Log reasoning output generation.

        Args:
            input_context: Input that triggered the reasoning
            output_plan: Generated plan output
            reasoning_steps: Steps taken during reasoning
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "log_type": "reasoning_output",
            "input_context": input_context,
            "output_plan": output_plan,
            "reasoning_steps": reasoning_steps
        }
        self._write_log_entry(self.reasoning_log, entry)
        self._write_audit_trail_entry(entry)

    def log_plan_creation(self, plan_id: str, objective: str, actions: List[str],
                         required_approvals: List[str], expected_outcome: str):
        """
        Log plan creation.

        Args:
            plan_id: Unique identifier for the plan
            objective: Objective of the plan
            actions: List of actions in the plan
            required_approvals: Actions requiring approval
            expected_outcome: Expected outcome of the plan
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "log_type": "plan_creation",
            "plan_id": plan_id,
            "objective": objective,
            "actions": actions,
            "required_approvals": required_approvals,
            "expected_outcome": expected_outcome
        }
        self._write_log_entry(self.planning_log, entry)
        self._write_audit_trail_entry(entry)

    def log_approval_decision(self, approval_id: str, plan_id: str,
                             approved_actions: List[str], approver: str, decision: str):
        """
        Log approval decision.

        Args:
            approval_id: Unique identifier for the approval
            plan_id: Associated plan ID
            approved_actions: List of actions approved
            approver: Identity of the approver
            decision: Approval decision (approved, rejected, etc.)
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "log_type": "approval_decision",
            "approval_id": approval_id,
            "plan_id": plan_id,
            "approved_actions": approved_actions,
            "approver": approver,
            "decision": decision
        }
        self._write_log_entry(self.approval_log, entry)
        self._write_audit_trail_entry(entry)

    def log_mcp_execution(self, execution_id: str, action_type: str,
                          action_params: Dict[str, Any], result: str, error: Optional[str] = None):
        """
        Log MCP server execution.

        Args:
            execution_id: Unique identifier for the execution
            action_type: Type of action executed
            action_params: Parameters for the action
            result: Result of the execution (success, failure)
            error: Error message if execution failed
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "log_type": "mcp_execution",
            "execution_id": execution_id,
            "action_type": action_type,
            "action_params": action_params,
            "result": result,
            "error": error
        }
        self._write_log_entry(self.execution_log, entry)
        self._write_audit_trail_entry(entry)

    def log_system_event(self, event_type: str, component: str, message: str,
                         details: Optional[Dict[str, Any]] = None):
        """
        Log general system events.

        Args:
            event_type: Type of system event
            component: Component that generated the event
            message: Event message
            details: Additional details about the event
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "log_type": "system_event",
            "event_type": event_type,
            "component": component,
            "message": message,
            "details": details or {}
        }
        self._write_log_entry(self.system_log, entry)
        self._write_audit_trail_entry(entry)

    def verify_log_integrity(self, log_file: Path) -> bool:
        """
        Verify the integrity of a log file by checking hashes.

        Args:
            log_file: Path to the log file to verify

        Returns:
            True if log is intact, False if tampering detected
        """
        if not log_file.exists():
            return False

        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                stored_hash = entry.get('hash')
                if not stored_hash:
                    continue

                # Calculate hash without the stored hash
                entry_copy = entry.copy()
                del entry_copy['hash']

                calculated_hash = self._calculate_hash(entry_copy)

                if stored_hash != calculated_hash:
                    return False
            except (json.JSONDecodeError, KeyError):
                return False

        return True