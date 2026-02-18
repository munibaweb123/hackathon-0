---
id: "0014"
title: Odoo Accounting MCP Skill
stage: green
date: 2026-02-15
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: implement
labels: ["mcp", "odoo", "accounting", "json-rpc", "hitl", "invoicing", "erp"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/odoo-accounting-mcp/odoo_client.js
  - .claude/skills/odoo-accounting-mcp/invoice_generator.js
  - .claude/skills/odoo-accounting-mcp/mcp_server.js
  - .claude/skills/odoo-accounting-mcp/package.json
  - .claude/skills/odoo-accounting-mcp/odoo_config.example.json
  - .claude/skills/odoo-accounting-mcp/SKILL.md
tests:
  - manual: npm run inspect with MCP Inspector to test tool listing
  - manual: list_unpaid_invoices and get_account_balance (read-only, no Odoo needed for approval tests)
  - manual: create_invoice with HITL approval file verification in pending-approval/
---

## Prompt

Create an Agent Skill called "odoo-accounting-mcp" that integrates with Odoo Community Edition (v19+) for accounting operations. Requirements: MCP server using Odoo's JSON-RPC API, connect to local Odoo instance (http://localhost:8069), 6 MCP tools (create_invoice, record_payment, create_expense, get_account_balance, list_unpaid_invoices, create_partner), HITL approval for financial operations, invoice PDF generation via Odoo reporting, track operations in /Accounting/ folder, multi-currency support, log to /Logs/accounting.json. File structure: SKILL.md, mcp_server.js, odoo_client.js, invoice_generator.js, package.json, odoo_config.example.json.

## Response snapshot

Created 6 files in `.claude/skills/odoo-accounting-mcp/`:

1. **odoo_client.js** — Odoo JSON-RPC 2.0 wrapper using native fetch(). Handles authentication (common.login → uid), execute_kw for all ORM operations, session-based PDF report download, config loading from odoo_config.json or env vars, retry with exponential backoff, action logging to vault/Logs/accounting.json.

2. **invoice_generator.js** — Higher-level accounting logic built on OdooClient. Creates invoices (with partner auto-resolution, line items as one2many commands, multi-currency), confirms via action_post, downloads PDF via Odoo report engine. Records payments against invoices (auto-resolves journal by method). Creates expenses via hr.expense. Queries account balances by type (receivable/payable/bank/cash). Lists unpaid invoices. Creates partners. Saves records as markdown to vault/Accounting/{invoices,payments,expenses}/.

3. **mcp_server.js** — MCP server with stdio transport, 6 tools. Financial writes (create_invoice, record_payment, create_expense, create_partner) route through ApprovalHandler with risk levels (high for invoices/payments, medium for expenses/partners). Read-only tools (get_account_balance, list_unpaid_invoices) execute directly. Reuses ApprovalHandler from social-poster-mcp. Lazy client initialization.

4. **package.json** — Minimal deps: @modelcontextprotocol/sdk + dotenv. All Odoo calls via native fetch().

5. **odoo_config.example.json** — Connection template: url, db, username, password.

6. **SKILL.md** — Full documentation with all 6 tool schemas, approval workflow, architecture diagram, JSON-RPC protocol details, configuration options (JSON/env/Claude Desktop), vault folder structure, error handling, troubleshooting.

## Outcome

- ✅ Impact: Complete Odoo CE accounting integration with HITL approval for financial operations
- 🧪 Tests: Manual verification via MCP Inspector; requires running Odoo for full integration test
- 📁 Files: 6 files created in .claude/skills/odoo-accounting-mcp/
- 🔁 Next prompts: Install Odoo CE, configure credentials, npm install, test with MCP Inspector
- 🧠 Reflection: Reusing ApprovalHandler from social-poster-mcp avoided code duplication. JSON-RPC is simple enough that native fetch() works perfectly — no Odoo SDK needed.

## Evaluation notes (flywheel)

- Failure modes observed: None — clean implementation following established MCP pattern
- Graders run and results (PASS/FAIL): N/A — requires running Odoo instance for integration test
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add vendor bill support (account.move with move_type: "in_invoice")
