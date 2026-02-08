# Research: Silver Tier — Functional Assistant

**Branch**: `003-silver-tier-assistant` | **Date**: 2026-02-08 | **Plan**: [plan.md](./plan.md)

## Research Summary

This document consolidates research findings for the Silver Tier implementation, resolving all technical unknowns identified during planning.

---

## 1. WhatsApp Web Automation with Playwright

### Decision
Use Playwright for Python to automate WhatsApp Web for message monitoring and sending.

### Rationale
- WhatsApp Business Cloud API requires business verification (not suitable for personal accounts)
- Playwright provides robust browser automation with session persistence
- Aligns with hackathon architecture guide specification

### Implementation Pattern
```python
from playwright.async_api import async_playwright

class WhatsAppWatcher:
    async def initialize(self):
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context(
            storage_state="whatsapp_session.json"  # Persist session
        )
        self.page = await self.context.new_page()
        await self.page.goto("https://web.whatsapp.com")

    async def wait_for_qr_scan(self):
        # Wait for QR code to disappear (user scanned it)
        await self.page.wait_for_selector('[data-testid="qrcode"]', state='hidden', timeout=120000)

    async def save_session(self):
        await self.context.storage_state(path="whatsapp_session.json")

    async def get_new_messages(self):
        # Poll for unread message indicators
        unread = await self.page.query_selector_all('[aria-label*="unread"]')
        return [await self.extract_message(el) for el in unread]
```

### Session Management
- First launch: User must scan QR code manually
- Subsequent launches: Load `whatsapp_session.json` to restore session
- Session expires: Detect expired state, prompt user to re-authenticate

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| WhatsApp Business Cloud API | Requires business verification, not personal accounts |
| whatsapp-web.js (Node.js) | Additional runtime dependency; Python preferred for consistency |
| Selenium | Playwright has better async support and is more maintainable |

---

## 2. Claude API Reasoning Loop Patterns

### Decision
Use Claude claude-sonnet-4-20250514 with structured tool use for the reasoning loop.

### Rationale
- Claude claude-sonnet-4-20250514 balances cost and capability for business reasoning tasks
- Tool use enables structured action proposals
- Consistent with existing `claude_integration.py` patterns

### Implementation Pattern
```python
from anthropic import Anthropic

class ReasoningLoop:
    def __init__(self):
        self.client = Anthropic()
        self.model = "claude-sonnet-4-20250514"

    def analyze_event(self, event: dict) -> PlanMd:
        tools = [
            {
                "name": "propose_action",
                "description": "Propose an action for human approval",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action_type": {"type": "string", "enum": ["email_reply", "linkedin_post", "escalate", "archive"]},
                        "description": {"type": "string"},
                        "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                        "required_approval": {"type": "boolean"}
                    },
                    "required": ["action_type", "description", "risk_level", "required_approval"]
                }
            }
        ]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            tools=tools,
            messages=[{
                "role": "user",
                "content": f"Analyze this event and propose appropriate actions:\n\n{json.dumps(event)}"
            }]
        )

        return self.extract_plan(response)
```

### Prompt Engineering
- System prompt includes business context from user settings
- Event context includes source, timestamp, and raw content
- Output structured as Plan.md with checkboxes for approval

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| Claude Opus 4.5 | Higher cost; claude-sonnet-4-20250514 sufficient for reasoning tasks |
| GPT-4o | Not specified in constitution; Claude preferred |
| Local LLM | Insufficient reasoning capability for business analysis |

---

## 3. LinkedIn API Posting Workflow

### Decision
Use LinkedIn Marketing API v2 with OAuth 2.0 3-legged flow for posting.

### Rationale
- Official API with proper rate limits and compliance
- OAuth 2.0 provides secure, revocable user authorization
- Existing dashboard OAuth flow can be extended

### Implementation Pattern
```python
import requests

class LinkedInPoster:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.linkedin.com/v2"

    def get_profile_urn(self) -> str:
        response = requests.get(
            f"{self.base_url}/userinfo",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        return f"urn:li:person:{response.json()['sub']}"

    def create_post(self, text: str) -> dict:
        urn = self.get_profile_urn()

        payload = {
            "author": urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        response = requests.post(
            f"{self.base_url}/ugcPosts",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            },
            json=payload
        )

        return response.json()
```

### OAuth Scopes Required
- `openid` - OpenID Connect
- `profile` - Basic profile info
- `email` - Email address
- `w_member_social` - Write permission for posts

### Rate Limits
- 100 posts per day per member
- 150,000 API calls per day per application
- Exponential backoff on 429 responses

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| LinkedIn Share API (legacy) | Deprecated; UGC Posts API is current standard |
| Third-party posting services | Additional cost; direct API preferred |
| Selenium automation | Against LinkedIn ToS; API is compliant |

---

## 4. Gmail API Polling Best Practices

### Decision
Use Gmail API with incremental sync (history.list) for efficient polling.

### Rationale
- Incremental sync avoids re-fetching entire mailbox
- History ID tracks changes since last sync
- Push notifications possible but add complexity

### Implementation Pattern
```python
from googleapiclient.discovery import build

class GmailWatcher:
    def __init__(self, credentials):
        self.service = build('gmail', 'v1', credentials=credentials)
        self.last_history_id = None

    def get_initial_history_id(self):
        profile = self.service.users().getProfile(userId='me').execute()
        self.last_history_id = profile['historyId']
        return self.last_history_id

    def get_new_messages(self):
        if not self.last_history_id:
            return self.get_recent_messages()

        try:
            history = self.service.users().history().list(
                userId='me',
                startHistoryId=self.last_history_id,
                historyTypes=['messageAdded']
            ).execute()

            messages = []
            for record in history.get('history', []):
                for msg in record.get('messagesAdded', []):
                    full_msg = self.service.users().messages().get(
                        userId='me',
                        id=msg['message']['id'],
                        format='full'
                    ).execute()
                    messages.append(full_msg)

            self.last_history_id = history.get('historyId', self.last_history_id)
            return messages

        except HttpError as e:
            if e.resp.status == 404:
                # History ID too old, resync
                return self.get_recent_messages()
            raise
```

### Quota Management
- 250 quota units per day for free tier
- messages.list: 5 units, messages.get: 5 units
- Batch requests reduce quota usage

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| Pub/Sub push notifications | Requires public webhook endpoint; adds complexity |
| Full mailbox scan each poll | Inefficient; quota exhaustion risk |
| IMAP/POP3 | Gmail API provides richer metadata and labels |

---

## 5. MCP Server Action Execution

### Decision
Extend existing FastAPI MCP server with action-specific handlers and approval validation.

### Rationale
- FastAPI already in use for MCP server
- Modular action handlers enable extensibility
- Approval token validation ensures human consent

### Implementation Pattern
```python
# Approval validation middleware
async def validate_approval(approval_id: str) -> ApprovalRecord:
    approval_path = Path(f"obsidian-vault/Approved/APPROVAL_REQUIRED_{approval_id}.md")
    if not approval_path.exists():
        raise HTTPException(403, "Action not approved")

    approval = parse_approval_file(approval_path)
    if approval.status != "approved":
        raise HTTPException(403, "Approval not granted")
    if approval.expires_at < datetime.utcnow():
        raise HTTPException(403, "Approval expired")

    return approval

# Action execution endpoint
@app.post("/execute/linkedin_post")
async def execute_linkedin_post(request: LinkedInPostRequest):
    approval = await validate_approval(request.approval_id)

    poster = LinkedInPoster(request.access_token)
    result = poster.create_post(request.content)

    # Log execution
    log_execution(
        action="linkedin_post",
        approval_id=request.approval_id,
        result=result,
        timestamp=datetime.utcnow()
    )

    return {"status": "published", "post_id": result.get("id")}
```

### Security Measures
- All actions require valid approval token
- Approval files moved to `Approved/` folder trigger execution
- Failed actions logged and user notified
- No automatic retries without human re-approval

---

## 6. Agent Skills Framework Extension

### Decision
Extend existing base skill pattern with Silver Tier specific skills.

### Rationale
- Existing `base_skill.py` provides consistent interface
- Modular design enables independent testing
- Skills compose into workflows naturally

### New Skills for Silver Tier
| Skill | Purpose | Input | Output |
|-------|---------|-------|--------|
| `LinkedInContentSkill` | Generate business-relevant posts | Business context, topics | Post draft |
| `EventTriageSkill` | Prioritize and route incoming events | Event file | Priority, routing decision |
| `ApprovalMonitorSkill` | Watch for approval status changes | Approval folder | Execution triggers |
| `WhatsAppSkill` | WhatsApp message handling | Incoming message | Response draft |

### Skill Composition Example
```python
async def handle_email_event(event: Event):
    # Triage the event
    priority = await EventTriageSkill().execute(event)

    # Generate plan based on priority
    plan = await PlanningSkill().execute(event, priority)

    # If requires response, draft it
    if plan.requires_response:
        draft = await CommunicationSkill().execute(event, plan)

    # Create approval request
    await ApprovalSystem().create_request(plan, draft)
```

---

## 7. Task Scheduler Configuration

### Decision
Use APScheduler for Python-based task scheduling.

### Rationale
- Pure Python, no external dependencies
- Supports cron-style and interval scheduling
- Integrates with async code

### Implementation Pattern
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

class TaskScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def configure_watchers(self, config: dict):
        # Gmail polling every 5 minutes
        self.scheduler.add_job(
            gmail_watcher.poll,
            IntervalTrigger(minutes=config.get('gmail_interval', 5)),
            id='gmail_watcher'
        )

        # LinkedIn polling every 15 minutes
        self.scheduler.add_job(
            linkedin_watcher.poll,
            IntervalTrigger(minutes=config.get('linkedin_interval', 15)),
            id='linkedin_watcher'
        )

        # WhatsApp continuous monitoring
        self.scheduler.add_job(
            whatsapp_watcher.poll,
            IntervalTrigger(seconds=30),
            id='whatsapp_watcher'
        )

        # Daily LinkedIn post at 9 AM
        self.scheduler.add_job(
            linkedin_poster.generate_daily_post,
            CronTrigger(hour=9, minute=0),
            id='daily_linkedin_post'
        )

    def start(self):
        self.scheduler.start()
```

### Persistence
- Store last run times in vault metadata
- Resume from last checkpoint on restart
- Skip missed tasks (no backlog accumulation)

---

## Summary of Decisions

| Area | Decision | Key Technology |
|------|----------|----------------|
| WhatsApp Integration | Playwright web automation | playwright-python |
| Claude Reasoning | Tool-use with claude-sonnet-4-20250514 | anthropic SDK |
| LinkedIn Posting | Marketing API v2 with OAuth | requests + OAuth 2.0 |
| Gmail Monitoring | Incremental sync with history.list | google-api-python-client |
| MCP Server | FastAPI with approval validation | FastAPI |
| Task Scheduling | APScheduler with cron/interval triggers | apscheduler |
| Agent Skills | Modular skill composition | Base class pattern |

All NEEDS CLARIFICATION items from Technical Context have been resolved.
