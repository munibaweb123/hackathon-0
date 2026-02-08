---
name: mcp-actions
description: MCP Server action execution skill. Handles approved external actions (email send, LinkedIn post, WhatsApp reply) through the controlled MCP server with audit logging.
---

# MCP Actions Skill

Executes approved external actions through the FastAPI-based MCP server with full audit trails.

## Architecture

```
Approval Watcher → ApprovalProcessor → MCP Server → External APIs
                                            ↓
                                    obsidian-vault/logs/
```

- **Action phase** of the Perception → Reasoning → Action pipeline
- Only executes actions that have valid, non-expired approvals
- All executions are logged with tamper-evident audit trail

## Key Files

| File | Purpose |
|------|---------|
| `agent-skills/mcp_server/server.py` | FastAPI MCP server |
| `agent-skills/mcp_server/actions/email_action.py` | Email send via Gmail API |
| `agent-skills/mcp_server/actions/linkedin_action.py` | LinkedIn posting |
| `agent-skills/mcp_server/actions/whatsapp_action.py` | WhatsApp reply via Playwright |
| `agent-skills/core/approval_processor.py` | Routes approved actions |

## Available Actions

| Action Type | Endpoint | Service |
|-------------|----------|---------|
| `email_send` | POST /execute/action | Gmail API |
| `linkedin_post` | POST /execute/action | LinkedIn API |
| `whatsapp_reply` | POST /execute/action | Playwright |
| `notification_send` | POST /execute/action | Internal |

## MCP Server Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/status` | Service status + uptime |
| POST | `/execute/action` | Execute approved action |
| POST | `/action/execute` | Gold Tier coordinator route |
| POST | `/validate/approval` | Validate approval token |
| GET | `/actions/{action_id}` | Get action result |

## Execution Flow

```python
1. Receive approved action from ApprovalProcessor
2. Validate approval token + expiry
3. Check action_type is in allowed_actions list
4. Check action is in approved_actions list
5. Execute via _execute_action_by_type()
6. Log result to execution_logs
7. Store result in action_results
8. Return success/failure
```

## Safety Controls

### Allowed Actions
```python
["email_send", "linkedin_post", "whatsapp_reply",
 "notification_send", "file_create_external", "calendar_event_create"]
```

### Disallowed Actions (Hard Block)
```python
["payment", "data_deletion", "irreversible_operation",
 "system_configuration_change", "user_privilege_modification"]
```

### DRY_RUN Mode
When `DRY_RUN=true`:
- Logs what WOULD be executed
- Does NOT call external APIs
- Returns success with `dry_run: true` flag

### DEV_MODE
When `DEV_MODE=true`:
- Extra validation on all inputs
- Verbose logging
- Rate limits more aggressive

## Audit Trail

Every execution creates an audit entry:
```json
{
  "approval_id": "<uuid>",
  "action_type": "linkedin_post",
  "plan_id": "<uuid>",
  "risk_level": "medium",
  "status": "success",
  "timestamp": "2026-02-08T14:30:00Z"
}
```

Stored in `obsidian-vault/logs/action_result_<id>.json`.

## Error Handling

| Error | Response | Recovery |
|-------|----------|----------|
| Invalid approval | 401 | Reject action |
| Disallowed action | 403 | Block + log security violation |
| Rate limited (429) | Retry-After header | Exponential backoff |
| Service unavailable | 503 | Queue for retry |
| Execution failure | 500 | Move to error folder |
