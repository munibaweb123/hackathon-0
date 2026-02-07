"""Core entities for the Personal AI Employee."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FileEntity:
    """Represents documents, data, and information processed by the system."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    type: str = ""  # document, task, config, etc.
    status: str = "new"  # new, processing, completed, pending_approval, archived
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OperationEntity:
    """Represents actions performed by the AI employee."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""  # read, write, process, categorize, etc.
    status: str = "pending"  # pending, in_progress, completed, failed, approved, rejected
    file_id: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: str = ""
    requires_approval: bool = False


@dataclass
class ApprovalEntity:
    """Represents human authorization for specific operations."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation_id: str = ""
    request_type: str = ""
    description: str = ""
    justification: str = ""
    options: List[Dict[str, str]] = field(default_factory=list)
    requested_at: datetime = field(default_factory=datetime.now)
    responded_at: Optional[datetime] = None
    approved: Optional[bool] = None
    approver_id: str = ""
    comments: str = ""
    selected_option: str = ""


@dataclass
class LogEntryEntity:
    """Represents record of system activities."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    level: str = "info"  # info, warn, error, critical, audit
    actor: str = ""  # ai_employee, human_operator, system
    action: str = ""
    details: str = ""
    file_ref: Optional[str] = None
    operation_ref: Optional[str] = None