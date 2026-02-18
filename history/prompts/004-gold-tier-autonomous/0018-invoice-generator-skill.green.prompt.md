---
id: "0018"
title: Invoice Generator Agent Skill
stage: green
date: 2026-02-17
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: developer
command: create-skill
labels: ["invoicing", "pdf", "python", "approval", "finance", "reportlab"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/invoice-generator/SKILL.md
  - .claude/skills/invoice-generator/invoice_generator.py
  - .claude/skills/invoice-generator/pdf_creator.py
  - .claude/skills/invoice-generator/reminder_scheduler.py
  - .claude/skills/invoice-generator/invoice_template.html
  - .claude/skills/invoice-generator/seed/Company_Info.md
  - .claude/skills/invoice-generator/seed/Rates.md
  - .claude/skills/invoice-generator/requirements.txt
tests:
  - "uv run invoice_generator.py --vault-path ../../../obsidian-vault --generate --customer 'Test Corp' --items '[{\"description\":\"Service\",\"quantity\":1,\"rate\":100}]'"
---

## Prompt

Create an Agent Skill called "invoice-generator" that creates professional invoices automatically.

Requirements: Detect client requests in /Needs_Action/ or scheduled creation, read rate information from /Accounting/Rates.md, calculate amounts based on project type and hours/deliverables, generate PDF using reportlab, include invoice number/date/due date/line items/subtotal/tax/total, use company branding from /Config/Company_Info.md, create approval request before sending, support recurring invoices (monthly retainers), track invoice status (draft/sent/paid/overdue), send reminders for overdue invoices.

Invoice workflow: Detect need → Calculate amount → Generate PDF → Create approval request → Wait for approval → Send via email MCP → Log in /Accounting/Invoices/.

File structure: SKILL.md, invoice_generator.py, pdf_creator.py, invoice_template.html, reminder_scheduler.py, requirements.txt.

## Response snapshot

Created 8 files in `.claude/skills/invoice-generator/`:

1. **invoice_generator.py** — Main UV-runnable orchestrator (PEP 723: reportlab, jinja2, python-dotenv, pyyaml). `InvoiceGenerator` class with 6 CLI modes: `--generate` (explicit items or from Rates.md), `--recurring` (monthly retainer processing), `--detect` (scan Needs_Action/), `--check-approvals` (process Approved/ files, create email actions), `--reminders` (delegate to ReminderScheduler), `--status` (update invoice status). Seeds config files to vault on first run.

2. **pdf_creator.py** — `InvoicePDFCreator` using reportlab platypus. Professional layout: branded header with logo support, INVOICE title, bill-to section, line items table (alternating row colors, right-aligned amounts), subtotal/tax/total section, payment info footer. Letter-sized, 0.75" margins, brand colors (#1a1a2e primary).

3. **reminder_scheduler.py** — `ReminderScheduler` with escalating reminder levels: gentle (1-7d), firm (8-14d), final (15-30d), escalation (30d+). Creates `Needs_Action/REMINDER_OVERDUE_{inv}_{level}.md` with suggested email templates for each level. Dedup via `Logs/invoice_reminders.json`.

4. **invoice_template.html** — Professional HTML email template (inline CSS for email client compatibility). Branded header, bill-to/amount-due, line items table, totals, payment info footer. Jinja2 variables for all dynamic content.

5. **seed/Company_Info.md** — Example company config: name, tagline, address, email, phone, website, tax_id, bank details, logo_path, payment terms, currency.

6. **seed/Rates.md** — Example rates config: invoice_prefix, default_tax_rate, 6 predefined rates (Web Dev $150/hr, UI/UX $125/hr, Consulting $200/hr, retainers $2500-$5000/mo), recurring_clients array.

7. **requirements.txt** — reportlab, jinja2, python-dotenv, pyyaml.

8. **SKILL.md** — Full documentation with workflow diagram, CLI modes, config format, vault data sources, reminder escalation table.

## Outcome

- ✅ Impact: Complete invoice lifecycle automation with PDF generation, HITL approval, email delivery, recurring support, and overdue reminders
- 🧪 Tests: `uv run invoice_generator.py --vault-path ../../../obsidian-vault --generate --customer "Test" --items '[{"description":"Service","quantity":1,"rate":100}]'`
- 📁 Files: 8 files created in .claude/skills/invoice-generator/
- 🔁 Next prompts: None specified
- 🧠 Reflection: reportlab's platypus API provides clean separation between layout building and rendering; seed config pattern ensures good first-run experience without requiring manual setup

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Manual verification PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add unit tests with mock vault; test PDF generation output
