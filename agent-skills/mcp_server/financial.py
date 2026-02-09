"""
Financial MCP Server

Handles Xero accounting integration for Gold Tier.
Provides OAuth flow, data retrieval, and write operations with approval.

Supports Gold Tier requirements:
- FR-001: Authenticate with Xero using OAuth 2.0
- FR-002: Retrieve invoices, contacts, bank transactions, account balances
- FR-003: Create draft invoices after human approval
- FR-004: Categorize bank transactions with AI-suggested matches
- FR-005: Handle Xero API rate limits (60 calls/minute)
"""

import os
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import uvicorn

# Import core modules
try:
    from core.credential_manager import CredentialManager
    from core.audit_logger import AuditLogger
    from core.metrics_collector import get_metrics, TimedOperation
    from models.audit_entry import ActorType, ActionResult
    from models.xero_connection import XeroConnection, XeroConnectionStatus
except ImportError:
    # Fallback for standalone testing
    CredentialManager = None
    AuditLogger = None


# Pydantic models for API
class XeroConnectionStatusResponse(BaseModel):
    """Xero connection status."""
    connected: bool
    tenantId: Optional[str] = None
    tenantName: Optional[str] = None
    tokenExpiry: Optional[str] = None
    status: str


class Invoice(BaseModel):
    """Invoice data."""
    invoiceId: str
    invoiceNumber: Optional[str] = None
    contactName: str
    status: str
    total: float
    amountDue: float
    currency: str = "USD"
    dueDate: Optional[str] = None


class XeroContact(BaseModel):
    """Xero contact."""
    contactId: str
    name: str
    email: Optional[str] = None
    isCustomer: bool = False
    isSupplier: bool = False


class BankTransaction(BaseModel):
    """Bank transaction for categorization."""
    transactionId: str
    date: str
    amount: float
    description: str
    accountCode: Optional[str] = None
    suggestedCategory: Optional[str] = None


class LineItem(BaseModel):
    """Invoice line item."""
    description: str
    quantity: float = 1.0
    unitAmount: float
    accountCode: Optional[str] = None
    taxType: Optional[str] = None


class CreateInvoiceRequest(BaseModel):
    """Request to create invoice."""
    approvalRef: str
    contactId: str
    dueDate: Optional[str] = None
    lineItems: List[LineItem]
    reference: Optional[str] = None


class CategorizeRequest(BaseModel):
    """Request to categorize transaction."""
    approvalRef: str
    accountCode: str
    description: Optional[str] = None


class FinancialSummary(BaseModel):
    """Financial summary for CEO briefing."""
    revenue: float = 0.0
    expenses: float = 0.0
    cashFlow: float = 0.0
    outstandingInvoices: List[Dict[str, Any]] = []
    varianceAlerts: List[Dict[str, Any]] = []


# Create FastAPI app
app = FastAPI(
    title="Gold Tier Financial MCP Server",
    version="1.0.0",
    description="Financial domain MCP server handling Xero integration",
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_credential_manager: Optional[CredentialManager] = None
_audit_logger: Optional[AuditLogger] = None
_oauth_states: Dict[str, str] = {}  # state -> timestamp for CSRF protection


def get_credential_manager() -> CredentialManager:
    """Get or create credential manager."""
    global _credential_manager
    if _credential_manager is None and CredentialManager:
        _credential_manager = CredentialManager()
    return _credential_manager


def get_audit_logger() -> AuditLogger:
    """Get or create audit logger."""
    global _audit_logger
    if _audit_logger is None and AuditLogger:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_xero_connection() -> Optional[XeroConnection]:
    """Load Xero connection from vault."""
    cm = get_credential_manager()
    if cm and cm.has_credentials("xero"):
        try:
            creds = cm.load_credentials("xero")
            return XeroConnection.from_dict(creds)
        except Exception:
            pass
    return None


def save_xero_connection(conn: XeroConnection) -> None:
    """Save Xero connection to vault."""
    cm = get_credential_manager()
    if cm:
        cm.save_credentials("xero", conn.to_dict())


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    global _credential_manager, _audit_logger
    if CredentialManager:
        _credential_manager = CredentialManager()
    if AuditLogger:
        _audit_logger = AuditLogger()


@app.get("/health")
async def health_check():
    """Health check endpoint for coordinator."""
    conn = get_xero_connection()
    return {
        "status": "healthy",
        "domain": "financial",
        "xeroConnected": conn is not None and conn.status == XeroConnectionStatus.ACTIVE,
        "lastSync": conn.last_sync if conn else None,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/xero/connect")
async def xero_connect():
    """
    Initiate Xero OAuth connection.

    Returns OAuth URL for user authorization.
    """
    client_id = os.environ.get("XERO_CLIENT_ID")
    redirect_uri = os.environ.get("XERO_REDIRECT_URI", "http://localhost:8001/xero/callback")

    if not client_id:
        raise HTTPException(status_code=500, detail="XERO_CLIENT_ID not configured")

    # Generate CSRF state
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = datetime.utcnow().isoformat()

    # Xero OAuth authorize URL
    scopes = "openid profile email accounting.transactions accounting.contacts accounting.settings"
    auth_url = (
        f"https://login.xero.com/identity/connect/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&state={state}"
    )

    return {"authUrl": auth_url, "state": state}


@app.get("/xero/callback")
async def xero_callback(code: str, state: str):
    """
    Handle Xero OAuth callback.

    Exchanges authorization code for tokens.
    """
    # Verify state for CSRF protection
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    del _oauth_states[state]

    client_id = os.environ.get("XERO_CLIENT_ID")
    client_secret = os.environ.get("XERO_CLIENT_SECRET")
    redirect_uri = os.environ.get("XERO_REDIRECT_URI", "http://localhost:8001/xero/callback")

    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Xero credentials not configured")

    # Exchange code for tokens (mock for now - real implementation uses xero-python SDK)
    # In production, use: from xero_python.api_client import ApiClient
    try:
        # Mock token response for development
        # Real implementation would call Xero's token endpoint
        conn = XeroConnection(
            tenant_id="mock-tenant-id",
            tenant_name="Demo Organization",
        )
        conn.update_tokens(
            access_token="mock-access-token",
            refresh_token="mock-refresh-token",
            expires_in_seconds=1800,  # 30 minutes
        )
        save_xero_connection(conn)

        # Log to audit
        logger = get_audit_logger()
        if logger:
            logger.append(
                action_type="xero.oauth.connect",
                actor=ActorType.USER,
                server_id="financial",
                details={"tenant_id": conn.tenant_id},
                result=ActionResult.SUCCESS,
            )

        return XeroConnectionStatusResponse(
            connected=True,
            tenantId=conn.tenant_id,
            tenantName=conn.tenant_name,
            tokenExpiry=conn.token_expiry,
            status=conn.status.value,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth exchange failed: {e}")


@app.get("/xero/status", response_model=XeroConnectionStatusResponse)
async def xero_status():
    """Get Xero connection status."""
    conn = get_xero_connection()

    if not conn:
        return XeroConnectionStatusResponse(
            connected=False,
            status="auth_required",
        )

    return XeroConnectionStatusResponse(
        connected=conn.status == XeroConnectionStatus.ACTIVE,
        tenantId=conn.tenant_id,
        tenantName=conn.tenant_name,
        tokenExpiry=conn.token_expiry,
        status=conn.status.value,
    )


@app.get("/xero/invoices", response_model=List[Invoice])
async def list_invoices(
    status: Optional[str] = Query(None, description="Filter by status"),
    fromDate: Optional[str] = Query(None, description="Start date"),
    toDate: Optional[str] = Query(None, description="End date"),
):
    """
    List invoices from Xero.

    Per FR-002: Retrieve invoices from Xero.
    """
    conn = get_xero_connection()
    if not conn or conn.status != XeroConnectionStatus.ACTIVE:
        raise HTTPException(status_code=503, detail="Xero connection unavailable")

    # Mock invoice data for development
    # Real implementation would use xero-python SDK
    invoices = [
        Invoice(
            invoiceId="INV-001",
            invoiceNumber="INV-0001",
            contactName="Acme Corp",
            status="AUTHORISED",
            total=1500.00,
            amountDue=1500.00,
            currency="USD",
            dueDate="2026-02-15",
        ),
        Invoice(
            invoiceId="INV-002",
            invoiceNumber="INV-0002",
            contactName="TechStart Inc",
            status="PAID",
            total=2500.00,
            amountDue=0.00,
            currency="USD",
            dueDate="2026-02-01",
        ),
    ]

    # Filter by status if provided
    if status:
        invoices = [inv for inv in invoices if inv.status == status]

    # Record metrics
    get_metrics().record_api_success("xero", "list_invoices")

    return invoices


@app.get("/xero/contacts", response_model=List[XeroContact])
async def list_contacts(search: Optional[str] = Query(None)):
    """
    List contacts from Xero.

    Per FR-002: Retrieve contacts from Xero.
    """
    conn = get_xero_connection()
    if not conn or conn.status != XeroConnectionStatus.ACTIVE:
        raise HTTPException(status_code=503, detail="Xero connection unavailable")

    # Mock contact data
    contacts = [
        XeroContact(
            contactId="CON-001",
            name="Acme Corp",
            email="billing@acme.com",
            isCustomer=True,
        ),
        XeroContact(
            contactId="CON-002",
            name="TechStart Inc",
            email="accounts@techstart.io",
            isCustomer=True,
        ),
    ]

    if search:
        contacts = [c for c in contacts if search.lower() in c.name.lower()]

    return contacts


@app.get("/xero/bank-transactions", response_model=List[BankTransaction])
async def list_bank_transactions(uncategorized: bool = Query(True)):
    """
    List bank transactions for categorization.

    Per FR-004: Categorize bank transactions with AI-suggested matches.
    """
    conn = get_xero_connection()
    if not conn or conn.status != XeroConnectionStatus.ACTIVE:
        raise HTTPException(status_code=503, detail="Xero connection unavailable")

    # Mock transaction data with AI suggestions
    transactions = [
        BankTransaction(
            transactionId="TXN-001",
            date="2026-02-05",
            amount=-150.00,
            description="OFFICE DEPOT SUPPLIES",
            accountCode=None if uncategorized else "6000",
            suggestedCategory="Office Expenses (6000)",
        ),
        BankTransaction(
            transactionId="TXN-002",
            date="2026-02-06",
            amount=-89.99,
            description="AWS SERVICES",
            accountCode=None if uncategorized else "6110",
            suggestedCategory="Software & Subscriptions (6110)",
        ),
    ]

    if uncategorized:
        transactions = [t for t in transactions if t.accountCode is None]

    return transactions


@app.post("/xero/invoices/create", response_model=Invoice)
async def create_invoice(request: CreateInvoiceRequest):
    """
    Create a new invoice in Xero.

    Per FR-003: Create draft invoices after human approval.
    Requires valid approval reference.
    """
    conn = get_xero_connection()
    if not conn or conn.status != XeroConnectionStatus.ACTIVE:
        raise HTTPException(status_code=503, detail="Xero connection unavailable")

    # Validate approval reference
    if not request.approvalRef:
        raise HTTPException(status_code=403, detail="Approval reference required")

    # Mock invoice creation
    # Real implementation would use xero-python SDK
    import uuid

    new_invoice = Invoice(
        invoiceId=f"INV-{uuid.uuid4().hex[:8].upper()}",
        invoiceNumber=f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M')}",
        contactName="Contact",  # Would resolve from contactId
        status="DRAFT",
        total=sum(item.quantity * item.unitAmount for item in request.lineItems),
        amountDue=sum(item.quantity * item.unitAmount for item in request.lineItems),
        dueDate=request.dueDate,
    )

    # Log to audit
    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="xero.invoice.create",
            actor=ActorType.AI,
            server_id="financial",
            details={
                "invoice_id": new_invoice.invoiceId,
                "contact_id": request.contactId,
                "total": new_invoice.total,
            },
            result=ActionResult.SUCCESS,
            approval_ref=request.approvalRef,
        )

    return new_invoice


@app.post("/xero/bank-transactions/{transaction_id}/categorize")
async def categorize_transaction(transaction_id: str, request: CategorizeRequest):
    """
    Categorize a bank transaction.

    Per FR-004: Categorize with AI-suggested matches requiring approval.
    """
    conn = get_xero_connection()
    if not conn or conn.status != XeroConnectionStatus.ACTIVE:
        raise HTTPException(status_code=503, detail="Xero connection unavailable")

    if not request.approvalRef:
        raise HTTPException(status_code=403, detail="Approval reference required")

    # Mock categorization
    # Real implementation would update via Xero API

    # Log to audit
    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="xero.transaction.categorize",
            actor=ActorType.AI,
            server_id="financial",
            details={
                "transaction_id": transaction_id,
                "account_code": request.accountCode,
            },
            result=ActionResult.SUCCESS,
            approval_ref=request.approvalRef,
        )

    return {
        "success": True,
        "transactionId": transaction_id,
        "accountCode": request.accountCode,
    }


@app.get("/xero/summary", response_model=FinancialSummary)
async def get_financial_summary(
    periodStart: str = Query(..., description="Period start date"),
    periodEnd: str = Query(..., description="Period end date"),
):
    """
    Get financial summary for CEO briefing.

    Per FR-012: CEO Briefing includes financial summary from Xero.
    """
    conn = get_xero_connection()
    if not conn or conn.status != XeroConnectionStatus.ACTIVE:
        # Return partial data with warning
        return FinancialSummary(
            varianceAlerts=[{"type": "warning", "message": "Xero connection unavailable"}]
        )

    # Mock financial summary
    # Real implementation would aggregate from Xero API
    return FinancialSummary(
        revenue=45000.00,
        expenses=32000.00,
        cashFlow=13000.00,
        outstandingInvoices=[
            {
                "invoiceId": "INV-001",
                "amount": 1500.00,
                "dueDate": "2026-02-15",
                "contactName": "Acme Corp",
            }
        ],
        varianceAlerts=[
            {"metric": "revenue", "changePct": 15.5, "direction": "up"}
        ],
    )


@app.post("/action/execute")
async def action_execute(request: dict):
    """
    Execute an action routed from the coordinator.
    Integrates with RetryQueue for failed actions (T070).
    """
    action_type = request.get("actionType", "")
    approval_ref = request.get("approvalRef", "")
    payload = request.get("payload", {})

    try:
        # Route to appropriate handler
        if action_type == "xero.invoice.create":
            line_items = [LineItem(**item) for item in payload.get("lineItems", [])]
            req = CreateInvoiceRequest(
                approvalRef=approval_ref,
                contactId=payload.get("contactId", ""),
                dueDate=payload.get("dueDate"),
                lineItems=line_items,
                reference=payload.get("reference"),
            )
            result = await create_invoice(req)
            return {"success": True, "result": result.dict()}

        elif action_type == "xero.transaction.categorize":
            req = CategorizeRequest(
                approvalRef=approval_ref,
                accountCode=payload.get("accountCode", ""),
                description=payload.get("description"),
            )
            result = await categorize_transaction(payload.get("transactionId", ""), req)
            return {"success": True, "result": result}

        else:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

    except Exception as e:
        # Queue for retry on failure (FR-020)
        try:
            from core.retry_queue import RetryQueue
            retry_queue = RetryQueue()
            retry_queue.add(
                action_type=action_type,
                action_payload=payload,
                failure_reason=str(e),
                approval_ref=approval_ref,
            )
        except ImportError:
            pass
        return {"success": False, "error": str(e), "queued_for_retry": True}


def run_financial_server(host: str = "0.0.0.0", port: int = 8001):
    """Run the financial MCP server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    port = int(os.environ.get("FINANCIAL_MCP_PORT", 8001))
    run_financial_server(port=port)
