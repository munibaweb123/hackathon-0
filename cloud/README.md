# Cloud Agent — Deployment Guide

The Cloud Agent runs on a free-tier Oracle Cloud VM (ARM, Ubuntu 22.04). It operates in **read-only mode**: monitors Gmail, generates draft replies and briefings, runs subscription audits, and syncs the Obsidian vault to a Git remote. It never sends, posts, or executes payments.

## Architecture

```
Oracle Cloud VM (ARM, Ubuntu 22.04)
├── cloud/agent.py              ← Entry point — manages all child processes
├── .claude/skills/
│   ├── gmail-watcher/          ← Polls Gmail (read-only), creates Drafts/email/
│   ├── health-monitor/         ← CPU/memory/disk checks, writes Signals/health/
│   ├── vault-sync/             ← Git push/pull every 5 minutes
│   └── ceo-briefing-generator/ ← Monday 7AM briefing → Drafts/briefings/
├── agent-skills/core/          ← Shared modules (security, audit, identity)
└── obsidian-vault/             ← Git-tracked vault (syncs with local agent)
```

## Prerequisites

- Ubuntu 22.04 (ARM or x86_64)
- Python 3.10+ with [`uv`](https://docs.astral.sh/uv/) installed
- Git configured with SSH access to your vault remote
- Gmail API credentials (read-only OAuth2 scope)
- (Optional) Docker 24+ and Docker Compose v2

## Option A: Direct Setup (Recommended for Development)

### 1. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### 2. Configure the Cloud Agent

```bash
# From the repository root
cd cloud/

# Create your config from the example
cp config.example.yaml config.yaml

# Required edits in config.yaml:
#   vault.path        → absolute path to your obsidian-vault/
#   vault.git_remote  → your Git remote URL (e.g. git@github.com:you/vault.git)
#   credentials.store_path → path to your encrypted credentials file
```

### 3. Set Up Credentials

```bash
# Set the encryption key (generate once and save securely)
export CREDENTIAL_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "Save this key somewhere safe: $CREDENTIAL_KEY"

# Copy the example credential file
ls credentials/
# Edit credentials with your read-only Gmail OAuth token
```

Gmail OAuth setup (read-only scope only):

1. Go to [Google Cloud Console](https://console.cloud.google.com) → Credentials → OAuth 2.0 Client IDs
2. Create a Desktop application credential
3. Download `credentials.json` to `cloud/credentials/`
4. Run the watcher once to complete OAuth: `uv run ../.claude/skills/gmail-watcher/gmail_watcher.py --once`
5. The token (read-only scope) is saved to `cloud/credentials/token.json`

### 4. Start the Cloud Agent

```bash
# Single run (test mode)
uv run agent.py --once

# Continuous mode (foreground)
uv run agent.py

# Background with nohup
nohup uv run agent.py >> /var/log/cloud-agent.log 2>&1 &
```

---

## Option B: Docker Compose (Recommended for Production)

### docker-compose.yml

```yaml
version: "3.9"

services:
  cloud-agent:
    build:
      context: ..
      dockerfile: cloud/Dockerfile
    container_name: ai-employee-cloud
    restart: unless-stopped

    environment:
      - CREDENTIAL_KEY=${CREDENTIAL_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

    volumes:
      # Mount the Obsidian vault (Git repo on the host)
      - ${VAULT_PATH}:/vault:rw
      # Mount SSH keys for Git push/pull
      - ~/.ssh:/root/.ssh:ro
      # Persist credentials
      - ./credentials:/app/cloud/credentials:ro
      # Persist config
      - ./config.yaml:/app/cloud/config.yaml:ro

    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

    healthcheck:
      test: ["CMD", "python3", "-c", "import os; open(os.environ.get('VAULT_PATH','/vault') + '/Signals/agents/cloud-001.yaml')"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
```

Save as `cloud/docker-compose.yml`, then:

```bash
# Copy and configure environment
cat > cloud/.env << 'EOF'
CREDENTIAL_KEY=your-fernet-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
VAULT_PATH=/absolute/path/to/obsidian-vault
EOF

# Build
docker compose -f cloud/docker-compose.yml build

# Start
docker compose -f cloud/docker-compose.yml up -d

# Logs
docker compose -f cloud/docker-compose.yml logs -f

# Stop
docker compose -f cloud/docker-compose.yml down
```

---

## Option C: systemd (Recommended for Bare-Metal Production)

```bash
# Copy the service file
sudo cp systemd/cloud-agent.service /etc/systemd/system/

# Edit the service file with your actual paths
sudo nano /etc/systemd/system/cloud-agent.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable cloud-agent
sudo systemctl start cloud-agent

# Check status
sudo systemctl status cloud-agent

# View logs
sudo journalctl -u cloud-agent -f
```

Contents of `systemd/cloud-agent.service`:

```ini
[Unit]
Description=AI Employee Cloud Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-employee
ExecStart=/home/ubuntu/.local/bin/uv run cloud/agent.py
Restart=on-failure
RestartSec=30
Environment=CREDENTIAL_KEY=your-key-here
Environment=ANTHROPIC_API_KEY=sk-ant-your-key-here
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

---

## Vault Folder Structure (Cloud Zone)

The cloud agent can only write to these folders (enforced by SecurityBoundary):

```
obsidian-vault/
├── Needs_Action/cloud/leads/   ← Lead files from email detection
├── Drafts/
│   ├── email/                  ← Draft replies from gmail-watcher
│   ├── social/                 ← Social post drafts (Monday generation)
│   ├── payments/               ← Payment draft files
│   └── briefings/              ← CEO Monday briefing
├── Signals/
│   ├── health/                 ← Health alerts from health-monitor
│   ├── agents/                 ← Heartbeat files (cloud-001.yaml)
│   └── sync/                   ← Sync conflict flags
├── Updates/                    ← General update notifications
├── Logs/
│   ├── sync/                   ← Sync event logs (JSON)
│   └── health/                 ← Health check history
└── audit/
    └── cloud-audit.jsonl       ← Hash-chained audit log (append-only)
```

**Write-denied paths** (cloud agent will raise SecurityBoundary error):
- `Pending_Approval/` — local agent only
- `Approved/` — local agent only
- `Done/` — local agent only
- `Dashboard.md` — local agent only

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| monday-briefing | 7:00 AM Monday | CEO briefing → `Drafts/briefings/` |
| subscription-audit | 8:00 AM 1st of month | Recurring expense analysis |
| draft-expiration | Every hour | Archive drafts older than 48h |
| health-check | Every 60 seconds | CPU/memory/disk/API checks |
| vault-sync | Every 5 minutes | Git push/pull to remote |
| invoice-due-scan | 9:00 AM Mon-Fri | Check invoices due within 3 days |

---

## Monitoring

### Check Agent Health

```bash
# Via systemd
sudo systemctl status cloud-agent

# Via vault heartbeat (should update every 5 min)
cat obsidian-vault/Signals/agents/cloud-001.yaml

# Via health alerts
ls obsidian-vault/Signals/health/

# Via audit log (most recent entries)
tail -5 obsidian-vault/audit/cloud-audit.jsonl | python3 -m json.tool
```

### Verify Audit Log Integrity

```bash
uv run agent-skills/core/audit_logger.py --verify --agent cloud-001 --vault-path obsidian-vault/
```

### Resource Limits (Free-Tier Oracle Cloud ARM)

The health-monitor enforces these thresholds (configurable in `config.yaml`):

| Resource | Threshold | Action |
|----------|-----------|--------|
| CPU | 80% | Write `Signals/health/ALERT_cpu_*.yaml` |
| Memory | 80% | Write `Signals/health/ALERT_memory_*.yaml` |
| Disk | 90% | Write `Signals/health/ALERT_disk_*.yaml` |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No heartbeat file | vault-sync not running, Git remote unreachable | Check Git SSH keys: `ssh -T git@github.com` |
| No email drafts | Gmail OAuth token expired or wrong scope | Delete `credentials/token.json`, re-run OAuth |
| `SecurityBoundary` error | Agent trying to write to forbidden path | Check `config.yaml` write_allowed_paths |
| High CPU alerts | gmail-watcher polling too fast | Increase `gmail.poll_interval_seconds` in config |
| Sync conflicts | Concurrent writes to same file | Check `Signals/sync/` for conflict details |
| Draft not expiring | draft-expiration sweeper disabled | Enable in `config.yaml` processes section |
