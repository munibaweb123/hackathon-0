# Local Agent — Setup Guide

The Local Agent runs on the CEO's trusted machine. It has **full credentials** and can approve and execute actions: send emails, post to social media, execute payments, and reply via WhatsApp. All sensitive actions require explicit approval via the dashboard or vault files.

## Architecture

```
CEO's Machine (macOS / Windows / Linux)
├── local/agent.py              ← Entry point — manages all child processes
├── .claude/skills/
│   ├── approval-manager/       ← Monitors Pending_Approval/, routes approved actions
│   ├── vault-sync/             ← Git push/pull every 5 minutes
│   ├── whatsapp-watcher/       ← Playwright monitors WhatsApp Web
│   ├── email-sender-mcp/       ← MCP server — sends emails (port 3001)
│   ├── social-poster-mcp/      ← MCP server — FB/Instagram/Twitter (port 3002)
│   └── payment-handler-mcp/    ← MCP server — payments (port 3003)
├── agent-skills/core/          ← Shared modules (security, audit, identity)
├── obsidian-vault/             ← Git-tracked vault (syncs with cloud agent)
└── dashboard/                  ← Next.js dashboard at localhost:3000
```

## Prerequisites

- macOS 12+, Windows 11 (WSL2), or Ubuntu 22.04
- Python 3.10+ with [`uv`](https://docs.astral.sh/uv/) installed
- Node.js 18+ (for MCP servers and dashboard)
- Git configured with SSH access to your vault remote
- Credentials for Gmail, LinkedIn, Twitter, Facebook, Stripe, PayPal
- Playwright browser (auto-installed for WhatsApp watcher)
- [Obsidian](https://obsidian.md) (optional but recommended for vault browsing)

---

## Quick Setup Script

Run this from the repository root to set up the local agent:

```bash
#!/usr/bin/env bash
# local/setup.sh — Run from repository root

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_DIR="$REPO_ROOT/local"

echo "=== AI Employee — Local Agent Setup ==="
echo "Repo root: $REPO_ROOT"
echo ""

# 1. Check prerequisites
echo "Checking prerequisites..."
command -v uv >/dev/null 2>&1 || { echo "ERROR: uv not installed. Run: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not installed. Install from https://nodejs.org/"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ERROR: git not installed."; exit 1; }
echo "  [OK] uv, node, git found"

# 2. Install Python dependencies
echo ""
echo "Installing Python dependencies..."
cd "$LOCAL_DIR"
uv sync
echo "  [OK] Python dependencies installed"

# 3. Install Node.js MCP server dependencies
echo ""
echo "Installing MCP server dependencies..."
for mcp_dir in email-sender-mcp social-poster-mcp payment-handler-mcp; do
    skill_dir="$REPO_ROOT/.claude/skills/$mcp_dir"
    if [ -d "$skill_dir" ]; then
        echo "  Installing $mcp_dir..."
        cd "$skill_dir" && npm install --silent
        echo "  [OK] $mcp_dir"
    fi
done

# 4. Install Playwright browsers (for WhatsApp watcher)
echo ""
echo "Installing Playwright browser..."
uv run playwright install chromium
echo "  [OK] Playwright chromium installed"

# 5. Install dashboard dependencies
echo ""
echo "Installing dashboard dependencies..."
cd "$REPO_ROOT/dashboard"
npm install --silent
echo "  [OK] Dashboard dependencies installed"

# 6. Configure local agent
echo ""
cd "$LOCAL_DIR"
if [ ! -f "config.yaml" ]; then
    cp config.example.yaml config.yaml
    echo "  [CREATED] local/config.yaml — Edit with your vault path and credential paths"
else
    echo "  [EXISTS] local/config.yaml"
fi

# 7. Check vault structure
echo ""
echo "Checking vault structure..."
VAULT_PATH=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c['vault']['path'])" 2>/dev/null || echo "")
if [ -z "$VAULT_PATH" ] || [ "$VAULT_PATH" = "/path/to/obsidian-vault" ]; then
    echo "  [WARN] Vault path not configured in config.yaml. Update vault.path before starting."
elif [ -d "$VAULT_PATH" ]; then
    echo "  [OK] Vault found: $VAULT_PATH"
else
    echo "  [WARN] Vault path does not exist: $VAULT_PATH (will be created on first run)"
fi

# 8. Check .env
if [ ! -f "$REPO_ROOT/.env" ]; then
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env" 2>/dev/null || true
    echo ""
    echo "  [CREATED] .env — Fill in your API keys before starting"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit local/config.yaml — set vault.path and vault.git_remote"
echo "  2. Edit .env — set ANTHROPIC_API_KEY and OAuth credentials"
echo "  3. Set CREDENTIAL_KEY: export CREDENTIAL_KEY=\$(python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
echo "  4. Run: uv run local/agent.py --dry-run   (validate config)"
echo "  5. Run: uv run local/agent.py              (start local agent)"
echo "  6. Run: cd dashboard && npm run dev        (start dashboard)"
```

Save as `local/setup.sh` and run with `bash local/setup.sh`.

---

## Step-by-Step Manual Setup

### 1. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # or restart terminal
```

### 2. Install Python Dependencies

```bash
cd local/
uv sync
```

### 3. Install MCP Server Dependencies

```bash
cd .claude/skills/email-sender-mcp && npm install
cd ../social-poster-mcp && npm install
cd ../payment-handler-mcp && npm install
```

### 4. Install Playwright (WhatsApp Watcher)

```bash
uv run playwright install chromium
```

### 5. Configure the Local Agent

```bash
cd local/
cp config.example.yaml config.yaml
```

Edit `config.yaml` — required fields:

| Field | Description |
|-------|-------------|
| `vault.path` | Absolute path to your Obsidian vault directory |
| `vault.git_remote` | Git remote URL (e.g. `git@github.com:you/vault.git`) |
| `credentials.store_path` | Path to your encrypted credentials file |
| `approval.payment_secondary_threshold` | Amount above which a second confirmation is required |

### 6. Set Up Credentials

```bash
# Generate and save the encryption key
export CREDENTIAL_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# Add to your shell profile: echo 'export CREDENTIAL_KEY=...' >> ~/.bashrc

# Set API keys in .env
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY, GMAIL_*, META_*, TWITTER_*, STRIPE_*, PAYPAL_*
```

### 7. WhatsApp Session (First Time)

```bash
# Run in visible mode to scan QR code
uv run .claude/skills/whatsapp-watcher/whatsapp_watcher.py \
  --vault-path ./obsidian-vault --once
# Scan the QR code with your phone
# Session is saved to whatsapp-session/
```

### 8. Start the Local Agent

```bash
# Validate config without starting
uv run local/agent.py --dry-run

# Start (foreground)
uv run local/agent.py

# Start dashboard (separate terminal)
cd dashboard && npm run dev
# Open http://localhost:3000
```

---

## Approval Workflow

All sensitive actions require approval. The local agent monitors the Obsidian vault for files placed in `Pending_Approval/local/` by the cloud agent, then awaits human decision.

```
Cloud Agent                          Local Agent (CEO)
────────────                         ─────────────────
Detects event
  → Creates Drafts/email/DRAFT_*.md
  → Syncs via Git (5 min)
                                     Dashboard shows new draft
                                     CEO reviews draft
                                     Approves → moves to Approved/
                                     (or) Rejects → moves to Done/expired/
                                     approval-manager detects move
                                     Routes to correct MCP handler:
                                       EmailHandler  → email-sender-mcp
                                       SocialHandler → social-poster-mcp
                                       PaymentHandler → payment-handler-mcp
                                     Action executed, receipt to Done/
```

### Approval Folders

| Folder | Action |
|--------|--------|
| `Pending_Approval/local/` | Files awaiting CEO review |
| `Approved/` | CEO approved — triggers automatic handler |
| `Done/` | Executed or rejected items |
| `Done/expired/` | Drafts that were never reviewed after 48h |

### Secondary Confirmation (Payments)

For payments above `approval.payment_secondary_threshold` (default: $1,000), the approval-manager creates a second approval request before executing. Both must be approved within 15 minutes of each other.

---

## Security Zones

The local agent enforces `SecurityBoundary` — it can only write to local-zone paths:

**Write-allowed paths:**
- `Pending_Approval/local/` — routes approval requests
- `Approved/` — executes approved actions
- `Done/` — archives completed/rejected items
- `Dashboard.md` — updates system status
- `Logs/` — activity logs
- `audit/local-*.jsonl` — audit trail

**Write-denied paths** (will raise SecurityBoundary error):
- `Drafts/` — cloud agent writes only
- `Signals/` — cloud agent writes only
- `Updates/` — cloud agent writes only

---

## Dashboard

The Next.js dashboard at `http://localhost:3000` provides:

| Page | Path | Description |
|------|------|-------------|
| Drafts Review | `/drafts` | Email, social, payment, briefing drafts pending review |
| Lead Pipeline | `/leads` | Captured leads by urgency and status |
| Sync Status | `/sync-status` | Last sync times, agent heartbeats, conflicts |
| Agent Topology | `/agent-topology` | Cloud/local agent status and capabilities |

```bash
cd dashboard && npm run dev
```

---

## MCP Servers

The local agent runs three MCP servers for external actions:

| Server | Port | Purpose |
|--------|------|---------|
| email-sender-mcp | 3001 | Send emails via Gmail API |
| social-poster-mcp | 3002 | Post to Facebook, Instagram, Twitter |
| payment-handler-mcp | 3003 | Execute payments (Stripe, PayPal, bank transfer) |

To add them to Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "email-sender": {
      "command": "node",
      "args": ["/path/to/.claude/skills/email-sender-mcp/mcp_server.js"],
      "env": { "VAULT_PATH": "/path/to/obsidian-vault" }
    },
    "social-poster": {
      "command": "node",
      "args": ["/path/to/.claude/skills/social-poster-mcp/mcp_server.js"],
      "env": { "VAULT_PATH": "/path/to/obsidian-vault" }
    },
    "payment-handler": {
      "command": "node",
      "args": ["/path/to/.claude/skills/payment-handler-mcp/mcp_server.js"],
      "env": { "VAULT_PATH": "/path/to/obsidian-vault" }
    }
  }
}
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No heartbeat from cloud | Cloud agent stopped or Git remote unreachable | SSH into VM, check `systemctl status cloud-agent` |
| Approval not triggering | Files not in `Pending_Approval/local/` | Check vault sync is running; verify file path |
| WhatsApp session expired | Long idle time | Delete `whatsapp-session/`, re-scan QR code |
| MCP server not responding | Node.js process crashed | Restart with `node .claude/skills/email-sender-mcp/mcp_server.js` |
| `SecurityBoundary` error | Agent writing to forbidden path | Check `local/config.yaml` security section |
| Dashboard blank | Next.js not started | Run `cd dashboard && npm run dev` |
| Payment not executing | Below secondary threshold approved, above not | Approve the second confirmation in dashboard |
