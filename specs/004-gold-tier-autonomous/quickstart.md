# Quickstart: Gold Tier — Autonomous Employee

**Feature Branch**: `004-gold-tier-autonomous`
**Prerequisites**: Silver Tier complete and running

---

## 1. Install Gold Tier Dependencies

```bash
# From repository root
pip install -r requirements.txt

# Additional Gold Tier packages
pip install xero-python>=3.0.0 tweepy>=4.14.0 cryptography>=42.0.0 prometheus-client>=0.19.0 httpx>=0.27.0
```

---

## 2. Configure Environment Variables

Create/update `.env` file in repository root:

```bash
# Existing Silver Tier config
VAULT_PATH=/path/to/obsidian-vault
ANTHROPIC_API_KEY=sk-ant-...

# Gold Tier: Master encryption key (generate once, store securely)
GOLD_MASTER_KEY=your-32-byte-base64-key

# Xero OAuth (from Xero Developer Portal)
XERO_CLIENT_ID=your-client-id
XERO_CLIENT_SECRET=your-client-secret
XERO_REDIRECT_URI=http://localhost:8001/xero/callback

# Meta/Facebook OAuth (from Meta Developer Portal)
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret
META_REDIRECT_URI=http://localhost:8002/meta/callback

# Twitter OAuth (from Twitter Developer Portal)
TWITTER_CLIENT_ID=your-client-id
TWITTER_CLIENT_SECRET=your-client-secret
TWITTER_REDIRECT_URI=http://localhost:8002/twitter/callback

# MCP Server Ports
COORDINATOR_PORT=8000
FINANCIAL_MCP_PORT=8001
SOCIAL_MCP_PORT=8002
COMMS_MCP_PORT=8003
```

Generate a master key:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

---

## 3. Create Vault Config Directory

```bash
mkdir -p $VAULT_PATH/config
mkdir -p $VAULT_PATH/contacts/unified
mkdir -p $VAULT_PATH/briefings/2026
mkdir -p $VAULT_PATH/audit/active
mkdir -p $VAULT_PATH/audit/archive
mkdir -p $VAULT_PATH/retry-queue
mkdir -p $VAULT_PATH/metrics
```

---

## 4. Start MCP Servers

Start all servers in separate terminals (or use process manager):

```bash
# Terminal 1: Coordinator (Port 8000)
python -m agent_skills.mcp_server.coordinator

# Terminal 2: Financial MCP (Port 8001)
python -m agent_skills.mcp_server.financial

# Terminal 3: Social MCP (Port 8002)
python -m agent_skills.mcp_server.social

# Terminal 4: Communication MCP (Port 8003) - existing from Silver
python -m agent_skills.mcp_server.server
```

Verify health:
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "servers": {...}}
```

---

## 5. Connect External Services

### Xero
1. Navigate to: `http://localhost:8001/xero/connect`
2. Complete OAuth flow in browser
3. Verify: `curl http://localhost:8001/xero/status`

### Facebook/Instagram
1. Navigate to: `http://localhost:8002/meta/connect`
2. Complete OAuth flow, grant page permissions
3. Verify: `curl http://localhost:8002/meta/status`

### Twitter
1. Navigate to: `http://localhost:8002/twitter/connect`
2. Complete OAuth flow
3. Verify: `curl http://localhost:8002/twitter/status`

---

## 6. Configure CEO Briefing Schedule

Edit `$VAULT_PATH/config/schedules.yaml`:

```yaml
ceo_briefing:
  enabled: true
  cron: "0 8 * * 0"  # Sunday 8:00 AM
  timezone: "America/New_York"
  notify_on_complete: true
```

---

## 7. Start Dashboard

```bash
cd dashboard
npm install  # if not done
npm run dev
```

Access at: `http://localhost:3000`

---

## 8. Verify Installation

Run the verification script:

```bash
python -m agent_skills.cli.main verify-gold
```

Expected output:
```
[✓] Coordinator MCP server healthy
[✓] Financial MCP server healthy
[✓] Social MCP server healthy
[✓] Communication MCP server healthy
[✓] Xero connection active
[✓] Facebook connection active
[✓] Instagram connection active
[✓] Twitter connection active
[✓] Audit log chain valid
[✓] Metrics endpoint responding
[✓] CEO briefing schedule configured

Gold Tier verification complete!
```

---

## 9. Test CEO Briefing Generation

Manually trigger a briefing:

```bash
curl -X POST http://localhost:8000/action/route \
  -H "Content-Type: application/json" \
  -d '{
    "actionType": "ceo.briefing.generate",
    "approvalRef": "manual-test",
    "payload": {"weekStart": "2026-02-03"}
  }'
```

Check generated file: `$VAULT_PATH/briefings/2026/week-06.md`

---

## Common Issues

### "Xero rate limit exceeded"
- Check `$VAULT_PATH/retry-queue/pending.yaml` for queued actions
- Wait for rate limit reset (60 calls/minute)

### "Meta token expired"
- Re-authenticate at `http://localhost:8002/meta/connect`
- Long-lived tokens last 60 days

### "Audit chain integrity error"
- Run: `python -m agent_skills.cli.main verify-audit-chain`
- If corrupted, restore from last valid backup

### "MCP server unhealthy"
- Check server logs: `tail -f logs/financial-mcp.log`
- Verify environment variables are set
- Restart individual server

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Dashboard                             │
│                   (Next.js @ :3000)                          │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    Coordinator MCP                           │
│                      (FastAPI @ :8000)                       │
│   - Routes actions to domain servers                         │
│   - Aggregates health status                                 │
│   - Exposes /metrics endpoint                                │
└────────────┬───────────────┬───────────────┬────────────────┘
             │               │               │
      ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
      │  Financial  │ │   Social    │ │   Comms     │
      │  MCP :8001  │ │  MCP :8002  │ │  MCP :8003  │
      │             │ │             │ │             │
      │  - Xero     │ │ - Facebook  │ │ - Gmail     │
      │             │ │ - Instagram │ │ - WhatsApp  │
      │             │ │ - Twitter   │ │ - LinkedIn  │
      └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
             │               │               │
      ┌──────▼───────────────▼───────────────▼──────┐
      │              Obsidian Vault                  │
      │  /config, /contacts, /briefings, /audit     │
      └─────────────────────────────────────────────┘
```

---

## Next Steps

1. Review the [Implementation Plan](./plan.md) for detailed architecture
2. Check [Tasks](./tasks.md) for implementation order (after `/sp.tasks`)
3. Connect real OAuth credentials for each platform
4. Configure CEO briefing preferences in vault
