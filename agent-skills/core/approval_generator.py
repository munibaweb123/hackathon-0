"""
Approval Generator Module

Creates APPROVAL_REQUIRED_*.md files in the pending-approval folder
when the system proposes sensitive actions that need human consent.

File-based approval workflow:
1. System creates APPROVAL_REQUIRED_<action>_<id>.md in pending-approval/
2. Human moves file to Approved/ or Rejected/ folder
3. Approval watcher detects the move and triggers/cancels action
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from pathlib import Path
import uuid

from core.vault_interface import VaultInterface
from core.logger import Logger


class ApprovalGenerator:
    """Generates APPROVAL_REQUIRED files for the file-based approval workflow."""

    def __init__(self, vault_interface: VaultInterface, logger: Logger):
        self.vault = vault_interface
        self.logger = logger

    def create_approval_request(
        self,
        action_type: str,
        description: str,
        context: str,
        plan_id: str = "",
        proposed_content: str = "",
        risk_level: str = "medium",
        expires_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Create an APPROVAL_REQUIRED file in the pending-approval folder.

        Args:
            action_type: Type of action (email_send, linkedin_post, whatsapp_reply, escalate)
            description: Human-readable action description
            context: Why this action is proposed
            plan_id: Parent plan ID (if from reasoning loop)
            proposed_content: Draft content (email body, post text, etc.)
            risk_level: low | medium | high
            expires_hours: Hours until approval expires (default 24)

        Returns:
            Dictionary with approval request metadata
        """
        approval_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=expires_hours)

        # Build filename
        action_slug = action_type.replace(" ", "_").lower()
        short_id = approval_id[:8]
        filename = f"APPROVAL_REQUIRED_{action_slug}_{short_id}.md"

        # Risk level emoji
        risk_emoji = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🔴 High"}.get(
            risk_level, "🟡 Medium"
        )

        # Build markdown content
        metadata = {
            "id": approval_id,
            "type": "approval_request",
            "action_type": action_type,
            "plan_id": plan_id or "null",
            "created": now.isoformat() + "Z",
            "expires": expires_at.isoformat() + "Z",
            "risk_level": risk_level,
            "status": "pending",
        }

        content_parts = [
            f"# Approval Request: {action_type.replace('_', ' ').title()}",
            "",
            f"**ID**: {approval_id}",
            f"**Plan**: {plan_id or 'N/A'}",
            f"**Created**: {now.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Expires**: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Risk Level**: {risk_emoji}",
            "",
            "## Proposed Action",
            "",
            f"**Type**: {action_type}",
            f"**Description**: {description}",
            "",
            "## Context",
            "",
            context,
            "",
        ]

        if proposed_content:
            content_parts.extend([
                "## Proposed Content",
                "",
                "```",
                proposed_content,
                "```",
                "",
            ])

        content_parts.extend([
            "## Decision",
            "",
            "**Status**: ⏳ Pending",
            "",
            "To approve: Move this file to the `/Approved` folder",
            "To reject: Move this file to the `/Rejected` folder",
            "",
            "---",
            "_Requires human approval before execution_",
        ])

        content = "\n".join(content_parts)

        # Write to vault
        file_path = self.vault.write_event_file(
            filename=filename,
            metadata=metadata,
            content=content,
            destination_folder="pending-approval",
        )

        self.logger.log_system_event(
            event_type="approval_created",
            component="approval_generator",
            message=f"Approval request created: {action_type} ({risk_level} risk)",
            details={
                "approval_id": approval_id,
                "action_type": action_type,
                "file_path": str(file_path),
                "expires_at": expires_at.isoformat(),
            },
        )

        return {
            "id": approval_id,
            "action_type": action_type,
            "description": description,
            "risk_level": risk_level,
            "status": "pending",
            "file_path": str(file_path),
            "filename": filename,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "plan_id": plan_id,
        }
