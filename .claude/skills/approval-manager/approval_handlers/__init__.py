"""
Approval Handlers — per-action-type routers that create action files
for downstream MCP skills to pick up.

Each handler implements:
  - can_handle(action_type: str) -> bool
  - execute(approval_data: dict, vault_path: Path) -> dict
"""

from .payment_handler import PaymentHandler
from .email_handler import EmailHandler
from .social_handler import SocialHandler
from .invoice_handler import InvoiceHandler

ALL_HANDLERS = [
    PaymentHandler(),
    EmailHandler(),
    SocialHandler(),
    InvoiceHandler(),
]

__all__ = [
    "PaymentHandler",
    "EmailHandler",
    "SocialHandler",
    "InvoiceHandler",
    "ALL_HANDLERS",
]
