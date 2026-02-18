---
id: "0021"
title: Approval Manager Agent Skill
stage: green
date: 2026-02-17
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: developer
command: create-skill
labels: ["approval", "hitl", "workflow", "monitoring"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/approval-manager/SKILL.md
  - .claude/skills/approval-manager/approval_manager.py
  - .claude/skills/approval-manager/notification_sender.py
  - .claude/skills/approval-manager/approval_handlers/__init__.py
  - .claude/skills/approval-manager/approval_handlers/payment_handler.py
  - .claude/skills/approval-manager/approval_handlers/email_handler.py
  - .claude/skills/approval-manager/approval_handlers/social_handler.py
  - .claude/skills/approval-manager/approval_handlers/invoice_handler.py
  - .claude/skills/approval-manager/requirements.txt
tests:
  - "uv run approval_manager.py --vault-path ../../../obsidian-vault --pending"
  - "uv run approval_manager.py --vault-path ../../../obsidian-vault --once"
  - "uv run approval_manager.py --vault-path ../../../obsidian-vault --expire-check"
---

## Prompt

Create an Agent Skill called "approval-manager" that handles human-in-the-loop workflows.

Requirements: Monitor pending-approval/ for approval requests, detect file moves to Approved/ or Rejected/, execute approved actions via per-type handlers, log rejections with reason, support approval expiration (24h default), send notifications for pending approvals, track approval history per action type, support delegation and bulk approvals, generate summary reports, update Dashboard.md.

Approval file format: standardized YAML frontmatter with type, action, status, created, expires, metadata. Workflow: agent creates approval -> manager monitors -> human decides -> manager executes/logs -> archive to Done/.

File structure: SKILL.md, approval_manager.py, approval_handlers/ (4 per-type modules), notification_sender.py, requirements.txt.

## Response snapshot

Created 9 files in `.claude/skills/approval-manager/`:

1. **approval_handlers/__init__.py** — Handler registry exporting ALL_HANDLERS list with PaymentHandler, EmailHandler, SocialHandler, InvoiceHandler.

2. **approval_handlers/payment_handler.py** — `PaymentHandler.execute()` creates `Needs_Action/EXECUTE_PAYMENT_*.md` with recipient, amount, currency, method fields for payment-handler-mcp pickup.

3. **approval_handlers/email_handler.py** — `EmailHandler.execute()` creates `Needs_Action/SEND_EMAIL_*.md` with to, subject, body, attachments for email-sender-mcp pickup.

4. **approval_handlers/social_handler.py** — `SocialHandler.execute()` creates `Needs_Action/POST_SOCIAL_{platform}_*.md` with content and media for social-poster-mcp pickup.

5. **approval_handlers/invoice_handler.py** — `InvoiceHandler.execute()` creates `Needs_Action/SEND_INVOICE_*.md` with invoice details and PDF attachment path for invoice-generator/email-sender-mcp pickup.

6. **notification_sender.py** — `NotificationSender` with 4 notification types: pending (new request), expiring_soon (<4h), expired (auto-rejected), bulk_summary (digest). Dedup via `Logs/approval_notifications.json`.

7. **approval_manager.py** — Main UV-runnable orchestrator (PEP 723: jinja2, python-dotenv, pyyaml). `ApprovalManager` class with: `process_once()` single poll cycle, `monitor()` continuous loop with SIGINT handler, `check_pending/approved/rejected/expired()` folder scanners, `approve_bulk()/reject_bulk()` bulk ops, `delegate()` frontmatter annotation, `generate_report()` summary stats, `show_history()` queryable log, `update_dashboard()` Dashboard.md section writer. 12 CLI modes.

8. **requirements.txt** — jinja2, python-dotenv, pyyaml.

9. **SKILL.md** — Full docs with workflow diagram, approval file format, handler routing table, CLI reference, notification types, delegation, bulk ops, Dashboard integration, vault data sources.

## Outcome

- ✅ Impact: Unified HITL approval orchestrator that centralizes the previously fragmented approval ecosystem across all skills
- 🧪 Tests: `--pending`, `--once`, `--expire-check`, `--report week`
- 📁 Files: 9 files created in .claude/skills/approval-manager/
- 🔁 Next prompts: Git commit all new skills
- 🧠 Reflection: Handlers create Needs_Action/ files (not direct MCP calls) — loose coupling lets each MCP skill independently pick up and process action files

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Manual verification PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Test with real approval files from social-poster-mcp and invoice-generator to verify YAML parsing compatibility
