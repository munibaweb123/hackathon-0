# Quickstart: Platinum Tier AI Employee

**Feature**: 005-platinum-tier-ai-employee
**Date**: 2026-02-18

## Prerequisites

- Python 3.10+ with `uv` installed
- Node.js 18+ (for dashboard)
- Git configured on both machines
- A Git remote repository (GitHub/GitLab) accessible by both agents
- Gmail API credentials (OAuth2 — read-only scope for cloud, full scope for local)
- An Obsidian vault (or willingness to use the provided vault structure)

## 1. Clone and Setup (Both Machines)

```bash
git clone <your-repo-url> ai-employee
cd ai-employee
```

## 2. Initialize the Obsidian Vault

```bash
# Create the Platinum Tier vault directory structure
mkdir -p obsidian-vault/{Needs_Action/cloud/leads,Drafts/{email,social,payments,briefings}}
mkdir -p obsidian-vault/{Signals/{health,auth,sync,agents},Updates}
mkdir -p obsidian-vault/{Pending_Approval/local,Approved,Done/{payments,expired}}
mkdir -p obsidian-vault/{Logs/{sync,health},audit}
```

## 3. Cloud Agent Setup (VM)

```bash
# Install Python dependencies
cd cloud/
uv sync

# Configure credentials (read-only tokens only!)
cp credentials/readonly-tokens.example.enc credentials/readonly-tokens.enc
# Edit with your read-only OAuth tokens

# Configure the cloud agent
cp config.example.yaml config.yaml
# Edit: set vault_path, gmail settings, sync remote URL

# Start the cloud agent
uv run agent.py
# Or via systemd:
sudo cp systemd/cloud-agent.service /etc/systemd/system/
sudo systemctl enable --now cloud-agent
```

## 4. Local Agent Setup (CEO's Machine)

```bash
# Install Python dependencies
cd local/
uv sync

# Configure credentials (full-access tokens)
cp credentials/sensitive-tokens.example.enc credentials/sensitive-tokens.enc
# Edit with your full OAuth tokens, payment credentials, etc.

# Configure the local agent
cp config.example.yaml config.yaml
# Edit: set vault_path, credential paths, approval settings

# Start the local agent
uv run agent.py
```

## 5. Dashboard Setup

```bash
cd dashboard/
npm install
npm run dev
# Open http://localhost:3000
```

## 6. Verify the System

1. **Check agent heartbeats**: Look for files in `obsidian-vault/Signals/agents/`
2. **Send a test email**: Send an email to the monitored inbox and verify a draft appears in `obsidian-vault/Drafts/email/` within 5 minutes
3. **Test vault sync**: Create a file on the cloud vault and verify it appears locally within 5 minutes
4. **Test approval flow**: Approve a draft via the dashboard and verify execution

## Key Configuration Files

| File | Purpose |
|------|---------|
| `cloud/config.yaml` | Cloud agent skills, schedules, sync settings |
| `local/config.yaml` | Local agent skills, credential paths, approval settings |
| `obsidian-vault/Company_Handbook.md` | Business context for draft generation |
| `obsidian-vault/Business_Goals.md` | Goals for social media and briefing content |

## Architecture Overview

```
┌─────────────────────┐     Git Sync      ┌─────────────────────┐
│    CLOUD AGENT      │ ←──── 5 min ────→ │    LOCAL AGENT      │
│  (Oracle Cloud VM)  │     (polling)      │  (CEO's Machine)    │
│                     │                    │                     │
│  gmail-watcher      │                    │  approval-manager   │
│  health-monitor     │                    │  email-sender-mcp   │
│  ceo-briefing-gen   │  ┌────────────┐   │  social-poster-mcp  │
│  subscription-audit │  │  Obsidian   │   │  payment-handler    │
│  vault-sync         │──│   Vault     │───│  whatsapp-watcher   │
│                     │  │  (Git repo) │   │  invoice-generator  │
│  READ-ONLY access   │  └────────────┘   │  vault-sync         │
│  No send/post/pay   │                    │                     │
└─────────────────────┘                    │  FULL access        │
                                           │  Approvals required │
                                           └─────────────────────┘
```

## Troubleshooting

- **No heartbeat files**: Check that `vault-sync` is running and Git remote is accessible
- **Drafts not appearing**: Verify Gmail API credentials have `gmail.readonly` scope
- **Sync conflicts**: Check `Signals/sync/` for flagged conflicts
- **Cloud agent won't start**: Check `Signals/health/` for resource alerts; verify Docker/systemd status
