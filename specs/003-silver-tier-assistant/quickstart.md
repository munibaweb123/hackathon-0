# Quickstart: Silver Tier — Functional Assistant

**Branch**: `003-silver-tier-assistant` | **Date**: 2026-02-08 | **Plan**: [plan.md](./plan.md)

## Prerequisites

Before starting Silver Tier development, ensure:

1. **Bronze Tier Foundation** is functional
   - File monitoring working (`src/file_monitor.py`)
   - Vault structure created (`obsidian-vault/`)
   - Approval system operational (`src/approval_system.py`)

2. **Python Environment**
   ```bash
   python --version  # Requires 3.8+
   pip install -r requirements.txt
   ```

3. **Node.js Environment** (for dashboard)
   ```bash
   node --version  # Requires 18+
   cd dashboard && npm install
   ```

4. **OAuth Credentials** (obtain before implementation)
   - Gmail: Google Cloud Console → APIs & Services → Credentials
   - LinkedIn: LinkedIn Developer Portal → My Apps → Create App

---

## Quick Setup

### 1. Environment Configuration

Create `.env` file at repository root:

```bash
# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Gmail OAuth (from Google Cloud Console)
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REDIRECT_URI=http://localhost:3000/api/auth/callback/google

# LinkedIn OAuth (from LinkedIn Developer Portal)
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
LINKEDIN_REDIRECT_URI=http://localhost:3000/api/linkedin/callback

# Server Configuration
MCP_SERVER_PORT=8000
DASHBOARD_PORT=3000
```

### 2. Vault Structure Verification

Ensure all required folders exist:

```bash
# Run from repository root
mkdir -p obsidian-vault/{inbox,processing,pending-approval,Approved,Rejected,completed,archive,error,plans,posts,logs}
mkdir -p obsidian-vault/config
```

### 3. Start Core Services

**Terminal 1: MCP Server**
```bash
cd agent-skills
uvicorn mcp_server.server:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2: Dashboard**
```bash
cd dashboard
npm run dev
```

**Terminal 3: Python Backend (Watchers + Reasoning)**
```bash
python -m agent_skills.cli.main start
```

---

## Development Workflow

### Adding a New Watcher

1. Create watcher class in `agent-skills/watchers/`:

```python
# agent-skills/watchers/my_watcher.py
from .watcher_base import WatcherBase, WatcherEvent

class MyWatcher(WatcherBase):
    @property
    def watcher_type(self) -> str:
        return "my_platform"

    async def detect_events(self) -> list[dict]:
        # Implement platform-specific detection
        pass

    def normalize_data(self, raw_data: dict) -> dict:
        # Convert to standard event format
        pass

    async def create_structured_file(self, event: WatcherEvent) -> str:
        # Write event to vault inbox
        pass
```

2. Register in scheduler (`agent-skills/scheduler/task_scheduler.py`)

3. Add dashboard page (`dashboard/src/app/myplatform/page.tsx`)

### Adding a New Agent Skill

1. Create skill class in `agent-skills/skills/`:

```python
# agent-skills/skills/my_skill.py
from ..core.base_skill import BaseSkill

class MySkill(BaseSkill):
    @property
    def id(self) -> str:
        return "my_skill"

    @property
    def name(self) -> str:
        return "My Custom Skill"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_data": {"type": "string"}
            },
            "required": ["input_data"]
        }

    @property
    def output_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            }
        }

    async def execute(self, input_data: dict) -> dict:
        # Implement skill logic
        return {"result": "done"}
```

2. Register skill in skill registry

3. Add tests in `tests/unit/skills/`

### Adding MCP Server Action

1. Create action handler in `agent-skills/mcp_server/actions/`:

```python
# agent-skills/mcp_server/actions/my_action.py
from ..approval_validator import validate_approval

async def execute_my_action(request: MyActionRequest) -> ActionResult:
    # Validate approval
    approval = await validate_approval(request.approval_id)

    # Execute action
    result = await perform_action(request)

    # Log execution
    log_execution(action="my_action", result=result)

    return ActionResult(status="success", result=result)
```

2. Add endpoint in `agent-skills/mcp_server/server.py`

3. Update OpenAPI spec in `specs/003-silver-tier-assistant/contracts/mcp-server-api.yaml`

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/unit/skills/test_reasoning_skill.py -v

# Run with coverage
pytest tests/ --cov=agent_skills --cov-report=html
```

### Integration Tests

```bash
# Test Gmail watcher (requires OAuth setup)
pytest tests/integration/test_gmail_watcher.py -v

# Test MCP server endpoints
pytest tests/integration/test_mcp_server.py -v
```

### Mock Mode Testing

All watchers support mock mode for testing without real credentials:

```python
# In tests or development
watcher = GmailWatcher(mode="mock")
events = await watcher.detect_events()  # Returns simulated events
```

---

## Key Code Paths

| Component | Entry Point | Description |
|-----------|-------------|-------------|
| Watchers | `agent-skills/watchers/` | Platform monitoring |
| Reasoning Loop | `agent-skills/skills/reasoning_skill.py` | Claude-powered analysis |
| Plan Generation | `agent-skills/skills/planning_skill.py` | Plan.md creation |
| MCP Server | `agent-skills/mcp_server/server.py` | External action execution |
| Scheduler | `agent-skills/scheduler/task_scheduler.py` | Task scheduling |
| Dashboard | `dashboard/src/app/` | Human interface |
| Approval Workflow | `dashboard/src/app/approvals/page.tsx` | Approval UI |

---

## Common Tasks

### Authenticate Gmail

1. Start dashboard: `cd dashboard && npm run dev`
2. Navigate to http://localhost:3000/gmail
3. Click "Connect Gmail"
4. Complete OAuth flow
5. Tokens stored automatically

### Authenticate LinkedIn

1. Navigate to http://localhost:3000/linkedin
2. Click "Connect LinkedIn"
3. Complete OAuth flow (ensure scopes include `w_member_social`)
4. Tokens stored automatically

### Set Up WhatsApp

1. Start WhatsApp watcher in non-headless mode:
   ```bash
   python -m agent_skills.watchers.whatsapp_watcher --headless=false
   ```
2. Scan QR code with WhatsApp mobile app
3. Session saved to `whatsapp_session.json`
4. Subsequent runs use saved session

### Configure Schedules

Edit `obsidian-vault/config/schedules.yaml`:

```yaml
schedules:
  - id: gmail_poll
    task_type: watcher_poll
    target_id: gmail_watcher
    schedule_type: interval
    interval_seconds: 300  # 5 minutes
    enabled: true

  - id: daily_linkedin_post
    task_type: content_generation
    target_id: linkedin_content_skill
    schedule_type: cron
    cron_expression: "0 9 * * *"  # 9 AM daily
    enabled: true
```

### Create Test Event

Drop a test file in the inbox:

```bash
cat > obsidian-vault/inbox/EMAIL_2026-02-08_120000_test123.md << 'EOF'
---
id: test-event-123
source_type: gmail
event_type: email_received
timestamp: 2026-02-08T12:00:00Z
detected_at: 2026-02-08T12:00:05Z
priority: medium
processing_status: new
---

# Test Email Event

**From**: test@example.com
**Subject**: Test Event

This is a test event for the reasoning loop.
EOF
```

The reasoning loop will detect and process this event.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| OAuth tokens expired | Re-authenticate via dashboard |
| WhatsApp disconnected | Re-scan QR code |
| MCP server 403 errors | Check approval file in `/Approved` folder |
| Reasoning loop timeout | Increase `CLAUDE_TIMEOUT` in `.env` |
| Event not detected | Check watcher logs in `obsidian-vault/logs/` |
| Plan not generated | Verify reasoning skill is registered |

---

## Next Steps

After setup, refer to:
- [spec.md](./spec.md) for detailed requirements
- [plan.md](./plan.md) for implementation approach
- [data-model.md](./data-model.md) for entity definitions
- [contracts/](./contracts/) for API specifications
