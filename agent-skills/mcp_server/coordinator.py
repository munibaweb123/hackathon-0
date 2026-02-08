"""
Coordinator MCP Server

Routes actions to domain-specific MCP servers (Financial, Social, Communication).
Provides health aggregation and unified action interface.

Supports Gold Tier requirements:
- FR-016: Operate separate MCP servers for different domains
- FR-017: Route actions to appropriate MCP server based on action type
- FR-018: Track health status of all MCP servers independently
- FR-019: Prevent routing to unhealthy MCP servers
- FR-030: Provide health check endpoint aggregating all MCP server statuses
"""

import os
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import uvicorn

from models.mcp_server import MCPServer, MCPDomain, MCPStatus
from core.audit_logger import AuditLogger
from core.metrics_collector import get_metrics
from models.audit_entry import ActorType, ActionResult


# Action type to domain mapping
ACTION_DOMAIN_MAP = {
    "xero": MCPDomain.FINANCIAL,
    "invoice": MCPDomain.FINANCIAL,
    "bank": MCPDomain.FINANCIAL,
    "financial": MCPDomain.FINANCIAL,
    "facebook": MCPDomain.SOCIAL,
    "instagram": MCPDomain.SOCIAL,
    "twitter": MCPDomain.SOCIAL,
    "meta": MCPDomain.SOCIAL,
    "social": MCPDomain.SOCIAL,
    "email": MCPDomain.COMMUNICATION,
    "gmail": MCPDomain.COMMUNICATION,
    "linkedin": MCPDomain.COMMUNICATION,
    "whatsapp": MCPDomain.COMMUNICATION,
}


class OverallHealth(str, Enum):
    """Overall coordinator health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServerHealth(BaseModel):
    """Individual server health."""
    status: str
    lastCheck: Optional[str] = None
    errorCount: int = 0


class HealthStatus(BaseModel):
    """Aggregated health status response."""
    status: str
    servers: Dict[str, ServerHealth]
    timestamp: str


class ActionRequest(BaseModel):
    """Action routing request."""
    actionType: str
    approvalRef: str
    payload: Optional[Dict[str, Any]] = None
    priority: str = "normal"


class ActionResponse(BaseModel):
    """Action routing response."""
    success: bool
    actionId: str
    serverId: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    timestamp: str
    auditRef: Optional[str] = None


class MCPServerInfo(BaseModel):
    """Server information response."""
    id: str
    domain: str
    endpoint: str
    status: str
    lastHealthAt: Optional[str] = None
    version: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str


# Create FastAPI app
app = FastAPI(
    title="Gold Tier Coordinator MCP Server",
    version="1.0.0",
    description="Routes actions to domain-specific MCP servers",
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Server registry
_servers: Dict[str, MCPServer] = {}
_http_client: Optional[httpx.AsyncClient] = None
_audit_logger: Optional[AuditLogger] = None

# Health check interval
HEALTH_CHECK_INTERVAL = 30


def init_servers() -> None:
    """Initialize server configurations."""
    global _servers

    financial_port = int(os.environ.get("FINANCIAL_MCP_PORT", 8001))
    social_port = int(os.environ.get("SOCIAL_MCP_PORT", 8002))
    comms_port = int(os.environ.get("COMMS_MCP_PORT", 8003))

    _servers = {
        "financial": MCPServer.create_financial_server(financial_port),
        "social": MCPServer.create_social_server(social_port),
        "communication": MCPServer.create_communication_server(comms_port),
    }


def get_domain_for_action(action_type: str) -> Optional[MCPDomain]:
    """Determine which domain handles an action type."""
    # Check first part of action type
    parts = action_type.lower().split(".")
    for part in parts:
        if part in ACTION_DOMAIN_MAP:
            return ACTION_DOMAIN_MAP[part]
    return None


def get_server_for_domain(domain: MCPDomain) -> Optional[MCPServer]:
    """Get server for a domain."""
    for server in _servers.values():
        if server.domain == domain:
            return server
    return None


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    global _http_client, _audit_logger

    init_servers()
    _http_client = httpx.AsyncClient(timeout=30.0)
    _audit_logger = AuditLogger()

    # Start health check task
    asyncio.create_task(health_check_loop())


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global _http_client
    if _http_client:
        await _http_client.aclose()


async def health_check_loop():
    """Background task to check server health."""
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        for server_id, server in _servers.items():
            await check_server_health(server)


async def check_server_health(server: MCPServer) -> bool:
    """Check health of a single server."""
    try:
        response = await _http_client.get(f"{server.endpoint}/health")
        if response.status_code == 200:
            server.record_success()
            get_metrics().set_mcp_server_health(server.id, server.domain.value, True)
            return True
        else:
            server.record_error()
            get_metrics().set_mcp_server_health(server.id, server.domain.value, False)
            return False
    except Exception:
        server.record_error()
        get_metrics().set_mcp_server_health(server.id, server.domain.value, False)
        return False


@app.get("/health", response_model=HealthStatus)
async def get_health():
    """Get aggregated health status of all MCP servers."""
    servers_health = {}
    healthy_count = 0

    for server_id, server in _servers.items():
        servers_health[server_id] = ServerHealth(
            status=server.status.value,
            lastCheck=server.last_health_at,
            errorCount=server.error_count,
        )
        if server.status == MCPStatus.HEALTHY:
            healthy_count += 1

    # Determine overall status
    if healthy_count == len(_servers):
        overall = OverallHealth.HEALTHY
    elif healthy_count > 0:
        overall = OverallHealth.DEGRADED
    else:
        overall = OverallHealth.UNHEALTHY

    return HealthStatus(
        status=overall.value,
        servers=servers_health,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics_endpoint():
    """Get Prometheus-compatible metrics."""
    return get_metrics().get_metrics_text()


@app.get("/servers", response_model=List[MCPServerInfo])
async def list_servers():
    """List all registered MCP servers."""
    return [
        MCPServerInfo(
            id=server.id,
            domain=server.domain.value,
            endpoint=server.endpoint,
            status=server.status.value,
            lastHealthAt=server.last_health_at,
            version=server.version,
        )
        for server in _servers.values()
    ]


@app.get("/servers/{server_id}/health", response_model=MCPServerInfo)
async def get_server_health(server_id: str):
    """Get health status of a specific server."""
    server = _servers.get(server_id)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")

    return MCPServerInfo(
        id=server.id,
        domain=server.domain.value,
        endpoint=server.endpoint,
        status=server.status.value,
        lastHealthAt=server.last_health_at,
        version=server.version,
    )


@app.post("/action/route", response_model=ActionResponse)
async def route_action(request: ActionRequest, background_tasks: BackgroundTasks):
    """Route an action to the appropriate domain server."""
    import uuid

    action_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    # Determine target domain
    domain = get_domain_for_action(request.actionType)
    if not domain:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action type: {request.actionType}",
        )

    # Get server for domain
    server = get_server_for_domain(domain)
    if not server:
        raise HTTPException(
            status_code=500,
            detail=f"No server configured for domain: {domain.value}",
        )

    # Check server health (circuit breaker)
    if not server.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Server unavailable: {server.id}",
        )

    # Forward request to domain server
    try:
        response = await _http_client.post(
            f"{server.endpoint}/action/execute",
            json={
                "actionType": request.actionType,
                "approvalRef": request.approvalRef,
                "payload": request.payload or {},
            },
        )

        if response.status_code == 200:
            result = response.json()

            # Log to audit
            if _audit_logger:
                entry = _audit_logger.append(
                    action_type=request.actionType,
                    actor=ActorType.SYSTEM,
                    server_id=server.id,
                    details={"payload": request.payload or {}},
                    result=ActionResult.SUCCESS,
                    approval_ref=request.approvalRef,
                )
                audit_ref = entry.id
            else:
                audit_ref = None

            return ActionResponse(
                success=True,
                actionId=action_id,
                serverId=server.id,
                result=result,
                timestamp=timestamp,
                auditRef=audit_ref,
            )
        else:
            # Log failure
            if _audit_logger:
                _audit_logger.append(
                    action_type=request.actionType,
                    actor=ActorType.SYSTEM,
                    server_id=server.id,
                    details={"payload": request.payload or {}},
                    result=ActionResult.FAILURE,
                    approval_ref=request.approvalRef,
                    error_message=f"Server returned {response.status_code}",
                )

            raise HTTPException(
                status_code=response.status_code,
                detail=f"Domain server error: {response.text}",
            )

    except httpx.RequestError as e:
        # Server unreachable
        server.record_error()

        if _audit_logger:
            _audit_logger.append(
                action_type=request.actionType,
                actor=ActorType.SYSTEM,
                server_id=server.id,
                details={"payload": request.payload or {}},
                result=ActionResult.FAILURE,
                approval_ref=request.approvalRef,
                error_message=str(e),
            )

        raise HTTPException(
            status_code=503,
            detail=f"Failed to reach server: {server.id}",
        )


def run_coordinator(host: str = "0.0.0.0", port: int = 8000):
    """Run the coordinator server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    port = int(os.environ.get("COORDINATOR_PORT", 8000))
    run_coordinator(port=port)
