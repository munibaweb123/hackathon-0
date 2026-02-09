"""
Xero Skill

Agent skill for Xero accounting operations.
Handles invoice management, contact lookup, and transaction categorization.

Supports Gold Tier requirements:
- FR-001 to FR-005: Xero integration
- FR-037: XeroSkill for financial operations
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import deque

from core.base_skill import BaseSkill, SkillResult


class RateLimiter:
    """
    Rate limiter for Xero API (60 calls/minute).

    Per FR-005: Handle Xero API rate limits with queuing.
    """

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.window_seconds = 60
        self.call_times: deque = deque()

    def can_call(self) -> bool:
        """Check if a call can be made without exceeding rate limit."""
        self._clean_old_calls()
        return len(self.call_times) < self.calls_per_minute

    def record_call(self) -> None:
        """Record that a call was made."""
        self.call_times.append(time.time())

    def wait_time(self) -> float:
        """Get seconds to wait before next call is allowed."""
        self._clean_old_calls()
        if len(self.call_times) < self.calls_per_minute:
            return 0

        oldest = self.call_times[0]
        return max(0, oldest + self.window_seconds - time.time())

    def _clean_old_calls(self) -> None:
        """Remove calls outside the window."""
        cutoff = time.time() - self.window_seconds
        while self.call_times and self.call_times[0] < cutoff:
            self.call_times.popleft()


class XeroSkill(BaseSkill):
    """
    Xero accounting operations skill.

    Provides:
    - Invoice listing and creation
    - Contact lookup
    - Bank transaction categorization
    - Financial summary for briefings

    Per FR-037: System MUST include XeroSkill for financial operations.
    """

    def __init__(self, vault_interface=None, logger=None, financial_mcp_url: str = None):
        """
        Initialize XeroSkill.

        Args:
            vault_interface: Interface for vault operations
            logger: Logger for auditability
            financial_mcp_url: URL of Financial MCP server
        """
        super().__init__("XeroSkill", vault_interface, logger)
        self.financial_mcp_url = financial_mcp_url or "http://localhost:8001"
        self._rate_limiter = RateLimiter(calls_per_minute=60)

    @property
    def id(self) -> str:
        return "xero"

    @property
    def description(self) -> str:
        return "Xero accounting operations: invoices, contacts, transactions"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "list_invoices",
                        "create_invoice",
                        "list_contacts",
                        "list_transactions",
                        "categorize_transaction",
                        "get_summary",
                        "check_connection",
                    ],
                    "description": "Operation to perform",
                },
                "params": {
                    "type": "object",
                    "description": "Operation-specific parameters",
                },
                "approval_ref": {
                    "type": "string",
                    "description": "Approval reference for write operations",
                },
            },
            "required": ["operation"],
        }

    @property
    def output_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {"type": "object"},
                "error": {"type": "string"},
            },
        }

    async def execute(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Execute a Xero operation.

        Args:
            input_data: Operation details including:
                - operation: The operation to perform
                - params: Operation parameters
                - approval_ref: Required for write operations

        Returns:
            SkillResult with operation outcome
        """
        start_time = time.time()

        try:
            operation = input_data.get("operation")
            params = input_data.get("params", {})
            approval_ref = input_data.get("approval_ref")

            # Check rate limit
            if not self._rate_limiter.can_call():
                wait_time = self._rate_limiter.wait_time()
                return SkillResult(
                    success=False,
                    error=f"Rate limit exceeded. Wait {wait_time:.1f} seconds.",
                    warnings=[f"Xero rate limit: {self._rate_limiter.calls_per_minute}/min"],
                )

            # Route to appropriate handler
            if operation == "list_invoices":
                result = await self._list_invoices(params)
            elif operation == "create_invoice":
                if not approval_ref:
                    return SkillResult(success=False, error="Approval reference required for create_invoice")
                result = await self._create_invoice(params, approval_ref)
            elif operation == "list_contacts":
                result = await self._list_contacts(params)
            elif operation == "list_transactions":
                result = await self._list_transactions(params)
            elif operation == "categorize_transaction":
                if not approval_ref:
                    return SkillResult(success=False, error="Approval reference required for categorize_transaction")
                result = await self._categorize_transaction(params, approval_ref)
            elif operation == "get_summary":
                result = await self._get_summary(params)
            elif operation == "check_connection":
                result = await self._check_connection()
            else:
                return SkillResult(success=False, error=f"Unknown operation: {operation}")

            # Record the call
            self._rate_limiter.record_call()

            execution_time = (time.time() - start_time) * 1000
            return SkillResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return SkillResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )

    async def _make_request(self, method: str, endpoint: str, json: dict = None) -> dict:
        """Make HTTP request to Financial MCP server."""
        import httpx

        url = f"{self.financial_mcp_url}{endpoint}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(url, params=json)
            else:
                response = await client.post(url, json=json)

            response.raise_for_status()
            return response.json()

    async def _list_invoices(self, params: dict) -> dict:
        """List invoices from Xero."""
        query_params = {}
        if "status" in params:
            query_params["status"] = params["status"]
        if "from_date" in params:
            query_params["fromDate"] = params["from_date"]
        if "to_date" in params:
            query_params["toDate"] = params["to_date"]

        return await self._make_request("GET", "/xero/invoices", query_params)

    async def _create_invoice(self, params: dict, approval_ref: str) -> dict:
        """Create a new invoice."""
        request_data = {
            "approvalRef": approval_ref,
            "contactId": params.get("contact_id"),
            "dueDate": params.get("due_date"),
            "lineItems": params.get("line_items", []),
            "reference": params.get("reference"),
        }
        return await self._make_request("POST", "/xero/invoices/create", request_data)

    async def _list_contacts(self, params: dict) -> dict:
        """List contacts from Xero and sync to unified contacts."""
        query_params = {}
        if "search" in params:
            query_params["search"] = params["search"]

        result = await self._make_request("GET", "/xero/contacts", query_params)

        # T080: Sync Xero contacts to unified contact registry
        try:
            from core.contact_matcher import ContactMatcher
            matcher = ContactMatcher()
            for contact in result.get("contacts", []):
                email = contact.get("email") or contact.get("emailAddress")
                name = contact.get("name") or contact.get("contactName", "")
                xero_id = contact.get("contactID", "")
                if email and xero_id:
                    matcher.create_or_update(
                        email=email,
                        display_name=name,
                        platform="xero",
                        platform_id=xero_id,
                        company=contact.get("companyNumber", ""),
                    )
        except (ImportError, Exception):
            pass

        return result

    async def _list_transactions(self, params: dict) -> dict:
        """List bank transactions."""
        query_params = {"uncategorized": params.get("uncategorized", True)}
        return await self._make_request("GET", "/xero/bank-transactions", query_params)

    async def _categorize_transaction(self, params: dict, approval_ref: str) -> dict:
        """Categorize a bank transaction."""
        transaction_id = params.get("transaction_id")
        request_data = {
            "approvalRef": approval_ref,
            "accountCode": params.get("account_code"),
            "description": params.get("description"),
        }
        return await self._make_request(
            "POST",
            f"/xero/bank-transactions/{transaction_id}/categorize",
            request_data,
        )

    async def _get_summary(self, params: dict) -> dict:
        """Get financial summary for CEO briefing."""
        query_params = {
            "periodStart": params.get("period_start", datetime.utcnow().strftime("%Y-%m-01")),
            "periodEnd": params.get("period_end", datetime.utcnow().strftime("%Y-%m-%d")),
        }
        return await self._make_request("GET", "/xero/summary", query_params)

    async def _check_connection(self) -> dict:
        """Check Xero connection status."""
        return await self._make_request("GET", "/xero/status", {})

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status."""
        return {
            "calls_remaining": self._rate_limiter.calls_per_minute - len(self._rate_limiter.call_times),
            "calls_per_minute": self._rate_limiter.calls_per_minute,
            "wait_time": self._rate_limiter.wait_time(),
        }
