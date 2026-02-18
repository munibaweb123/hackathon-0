---
name: health-monitor
description: Centralized system health monitoring for the AI Employee. Monitors processes, resources, API connectivity, and vault integrity. Auto-restarts crashed processes with exponential backoff, sends alerts via Needs_Action/ files, and updates Dashboard.md.
tools: []
tags:
  - monitoring
  - health
  - process-management
  - alerts
  - python
---

# Health Monitor

Centralized health monitoring for all AI Employee components. Monitors process liveness, system resources, API connectivity, and vault integrity. Auto-restarts crashed processes with exponential backoff (max 3/hour) and sends alerts via the existing Needs_Action/ notification pipeline.

## Quick Start

```bash
# 1. Single health check
uv run health_monitor.py --vault-path ../../obsidian-vault --once

# 2. Show current status
uv run health_monitor.py --vault-path ../../obsidian-vault --status

# 3. Continuous monitoring (every 60s)
uv run health_monitor.py --vault-path ../../obsidian-vault --monitor --interval 60
```

## Architecture

```
health-monitor/
├── health_monitor.py          # Main UV-runnable script (orchestrator)
├── process_manager.py         # PID tracking, liveness, restart with backoff
├── resource_checker.py        # Disk, memory, CPU checks (stdlib only)
├── alert_sender.py            # Alert notifications via Needs_Action/ files
├── requirements.txt
└── SKILL.md
```

## Health Check Types

### 1. Process Liveness

Monitors registered processes via PID files in `/tmp/ai-employee/`.

| Check | Method | Description |
|-------|--------|-------------|
| Running | `/proc/{pid}/` exists | Process is alive |
| Responsive | `os.kill(pid, 0)` | Process can receive signals |
| Uptime | PID file mtime | Time since last start |

### 2. System Resources

All resource checks use Python stdlib only — no psutil dependency.

| Resource | Method | Alert Threshold |
|----------|--------|----------------|
| Disk | `shutil.disk_usage()` | > 90% used |
| Memory | Parse `/proc/meminfo` | > 90% used |
| CPU | Sample `/proc/stat` + `os.getloadavg()` | > 90% usage |

### 3. Vault Accessibility

| Check | Method | Description |
|-------|--------|-------------|
| Readable | `Path.iterdir()` | Can list vault contents |
| Writable | Write + delete temp file | Can create files in vault |

### 4. API Connectivity

HTTP HEAD requests via `urllib.request` (no external deps).

Default endpoints:
- `google-apis` → `https://www.googleapis.com`
- `github` → `https://api.github.com`

Custom endpoints configurable via `config/health_endpoints.yaml`:
```yaml
endpoints:
  - name: odoo
    url: https://your-odoo.example.com
  - name: custom-api
    url: https://api.example.com/health
```

### 5. Custom Health Checks

Register shell commands as health checks. Exit code 0 = healthy.

```bash
# Register a custom check
uv run health_monitor.py --vault-path ../../obsidian-vault \
  --register my-service --command "curl -sf http://localhost:8080/health"
```

## Process Management

### Default Process Registry

| Process | Command | Max Restarts |
|---------|---------|-------------|
| gmail-watcher | `uv run gmail_watcher.py --monitor` | 3/hour |
| whatsapp-watcher | `uv run whatsapp_watcher.py --monitor` | 3/hour |
| filesystem-watcher | `uv run filesystem_watcher.py --watch` | 3/hour |
| approval-manager | `uv run approval_manager.py --monitor` | 3/hour |
| vault-sync | `uv run vault_sync.py --watch` | 3/hour |

Override with `config/processes.yaml`:
```yaml
processes:
  gmail-watcher:
    command: "uv run .claude/skills/gmail-watcher/gmail_watcher.py --vault-path {vault} --monitor"
    max_restarts: 5
  custom-service:
    command: "python my_service.py"
    max_restarts: 2
```

### Restart Policy

```
Process crashes → health monitor detects (PID check)
  ↓
Check restart budget (max 3/hour)
  ↓
If allowed:
  1. SIGTERM → wait 5s → SIGKILL if needed
  2. Exponential backoff: 5s → 15s → 45s
  3. Start process, write new PID file
  4. Send "info" alert: "restarted successfully"
  ↓
If budget exhausted:
  1. Send "critical" alert
  2. Do NOT restart
  3. Human intervention required
```

### PID Files

```
/tmp/ai-employee/
├── gmail-watcher.pid
├── whatsapp-watcher.pid
├── filesystem-watcher.pid
├── approval-manager.pid
└── vault-sync.pid
```

## Alert System

Alerts are created as markdown files in `Needs_Action/` with YAML frontmatter — the same pattern used by approval-manager's NotificationSender.

### Severity Levels

| Severity | When | Examples |
|----------|------|----------|
| `critical` | Component down, resource exhausted | Process won't restart, disk full |
| `warning` | Degraded performance, approaching limits | High memory, API unreachable |
| `info` | Informational | Process restarted successfully |

### Alert File Format

```markdown
---
type: health_alert
severity: critical
component: gmail-watcher
created: 2026-02-18T10:00:00+00:00
timestamp: 2026-02-18 10:00:00 UTC
auto_resolved: false
---

# Health Alert: gmail-watcher

**Severity:** CRITICAL
**Component:** gmail-watcher
**Time:** 2026-02-18 10:00:00 UTC

## Message

Process 'gmail-watcher' is DOWN and could not be restarted.

## Action Required

This is a **critical** alert. Immediate attention required.
```

### Alert Deduplication

- Alerts are deduped via `Logs/health_alerts.json`
- Same component + severity won't re-alert within 30-minute cooldown
- Alerts auto-clear when the issue resolves

## Dashboard.md Section

The health monitor writes a `## System Health` section to Dashboard.md:

```markdown
## System Health

**Status:** Healthy | **Last Check:** 2026-02-18 10:00 UTC

| Component | Status | Uptime | Last Check |
|-----------|--------|--------|------------|
| gmail-watcher | Running | 2d 4h | 2026-02-18 10:00 UTC |
| approval-manager | Running | 1d 12h | 2026-02-18 10:00 UTC |
| vault-sync | Running | 3d 1h | 2026-02-18 10:00 UTC |

**Resources:** Disk 45% | Memory 62% | CPU 15%

**Alerts:** 0 active
```

## CLI Reference

```
Monitoring:
  --monitor                 Continuous monitoring loop
  --interval N              Seconds between checks (default: 60)
  --once                    Single health check cycle

Status & Reports:
  --status                  Print health status summary
  --report                  Generate health report from logs
  --period PERIOD           Report period: 24h, 7d, 30d (default: 24h)

Process Management:
  --restart PROCESS         Manually restart a process
  --stop-process PROCESS    Stop a process
  --register NAME           Register a new process (requires --command)
  --command CMD             Command for --register
  --list-processes          List all registered processes

Common:
  --vault-path PATH         Obsidian vault path (default: ./obsidian-vault)
  --verbose, -v             Debug logging
```

## Monitoring Cycle

```
Every N seconds:
  1. Check all registered processes (PID liveness)
  2. Check system resources (disk, memory, CPU)
  3. Check vault accessibility (read/write)
  4. Check API connectivity (configurable endpoints)
  5. Auto-restart crashed processes (if within budget)
  6. Run custom health checks (shell commands)
  7. Send alerts for failures (Needs_Action/ files)
  8. Clear alerts for recovered components
  9. Update Dashboard.md
  10. Log results to Logs/health_monitor.json
```

## Vault Data Sources

| Source | Read/Write | Purpose |
|--------|------------|---------|
| `Needs_Action/ALERT_*.md` | Write | Health alert notifications |
| `Logs/health_monitor.json` | Write | Health check event log |
| `Logs/health_monitor.log` | Write | Rotating text log (5MB, 3 backups) |
| `Logs/health_alerts.json` | Read/Write | Alert dedup and history |
| `Logs/restart_history.json` | Read/Write | Process restart tracking |
| `Dashboard.md` | Write | System Health section |
| `config/processes.yaml` | Read | Process registry overrides |
| `config/health_endpoints.yaml` | Read | API endpoint configuration |
| `/tmp/ai-employee/*.pid` | Read/Write | Process PID files |

## Dependencies

- Python 3.10+
- `pyyaml` — YAML configuration support
- No psutil, no requests — stdlib only for resource and API checks

All declared in PEP 723 script header for automatic UV resolution.
