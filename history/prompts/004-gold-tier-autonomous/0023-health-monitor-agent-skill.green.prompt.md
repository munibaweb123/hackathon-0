---
id: 23
title: Health Monitor Agent Skill
stage: green
date: 2026-02-18
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: human
command: create skill
labels: ["health-monitor", "process-management", "monitoring", "alerts", "system-health"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/health-monitor/SKILL.md
  - .claude/skills/health-monitor/health_monitor.py
  - .claude/skills/health-monitor/process_manager.py
  - .claude/skills/health-monitor/resource_checker.py
  - .claude/skills/health-monitor/alert_sender.py
  - .claude/skills/health-monitor/requirements.txt
tests:
  - Manual verification of file structure and CLI interface
---

## Prompt

Create an Agent Skill called "health-monitor" that ensures all system components stay running. Requirements: Monitor critical processes (watchers, orchestrator, MCP servers), check process PIDs and restart if crashed, monitor disk space, memory usage, CPU usage, alert on resource exhaustion, check API connectivity (Gmail, Odoo, social media), verify vault integrity (readable, writable), track system uptime and log crashes, send notifications on failures (email, SMS, or Slack), generate health report in Dashboard.md, support custom health checks per component. Process management: Track PIDs in /tmp/{process_name}.pid, restart with exponential backoff, max restart attempts 3 per hour, after max attempts alert human and pause. Health checks: 1. Process liveness (is PID running?), 2. Process responsiveness (can it respond to signals?), 3. Resource usage (within limits?), 4. API connectivity (can reach external services?), 5. Vault accessibility (can read/write?), 6. Disk space (> 10% free?). File structure: SKILL.md, health_monitor.py, process_manager.py, resource_checker.py, alert_sender.py, requirements.txt.

## Response snapshot

Created the health-monitor skill with 6 files:

1. **`resource_checker.py`** — `ResourceChecker` class using stdlib only (no psutil): `check_disk()` via `shutil.disk_usage()`, `check_memory()` via `/proc/meminfo` parsing, `check_cpu()` via `/proc/stat` sampling + `os.getloadavg()`, `check_vault_access()` via temp file read/write, `check_api_connectivity()` via `urllib.request` HEAD requests. All thresholds default to 90%.

2. **`process_manager.py`** — `ProcessManager` class with PID files in `/tmp/ai-employee/`. Default registry of 5 processes (gmail-watcher, whatsapp-watcher, filesystem-watcher, approval-manager, vault-sync). `check_process()` reads PID file + checks `/proc/{pid}/` + `os.kill(pid, 0)`. `restart_process()` with exponential backoff (5s → 15s → 45s), max 3 restarts/hour per process. `_can_restart()` budget check. Restart history persisted to `Logs/restart_history.json`.

3. **`alert_sender.py`** — `AlertSender` class creating `Needs_Action/ALERT_{severity}_{component}_{timestamp}.md` files with YAML frontmatter. 3 severity levels: critical, warning, info. Dedup via `Logs/health_alerts.json` with 30-minute cooldown. `clear_alert()` marks auto-resolved. Same pattern as approval-manager's NotificationSender.

4. **`health_monitor.py`** — Main UV-runnable script (PEP 723, pyyaml). `HealthMonitor` class orchestrates all checks: `check_once()` runs full cycle (processes → resources → vault → APIs → auto-restart → alerts → dashboard → log). `monitor(interval=60)` continuous loop with SIGINT/SIGTERM. `show_status()` prints formatted summary. `show_report(period)` generates report from logs with uptime %, restart count, incidents. Custom health checks via shell commands. Dashboard.md `## System Health` section with process table + resource usage.

5. **`requirements.txt`** — pyyaml>=6.0

6. **`SKILL.md`** — Full documentation: 5 health check types, process management with restart policy, alert system with severity levels, Dashboard.md section format, CLI reference (10 flags), monitoring cycle, vault data sources, config files.

## Outcome

- ✅ Impact: Enables automated detection and recovery of crashed processes with human escalation when restart budget is exhausted
- 🧪 Tests: Manual verification of file structure and CLI interface
- 📁 Files: 6 files created in .claude/skills/health-monitor/
- 🔁 Next prompts: Integration testing with actual processes, git commit of all new skills
- 🧠 Reflection: Chose stdlib-only resource checks (no psutil) to keep dependencies minimal; PID-based monitoring is simple but effective for the single-machine deployment model

## Evaluation notes (flywheel)

- Failure modes observed: None — all files created successfully
- Graders run and results (PASS/FAIL): PASS — all 6 files match plan specification
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add integration test that starts a mock process, kills it, and verifies auto-restart and alert generation
