---
id: "0015"
title: Payment Handler MCP Skill
stage: green
date: 2026-02-15
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: implement
labels: ["mcp", "payments", "security", "fraud-detection", "hitl", "stripe", "paypal", "bank-transfer"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/payment-handler-mcp/fraud_detection.js
  - .claude/skills/payment-handler-mcp/approval_validator.js
  - .claude/skills/payment-handler-mcp/payment_clients/bank_transfer.js
  - .claude/skills/payment-handler-mcp/payment_clients/paypal_client.js
  - .claude/skills/payment-handler-mcp/payment_clients/stripe_client.js
  - .claude/skills/payment-handler-mcp/mcp_server.js
  - .claude/skills/payment-handler-mcp/package.json
  - .claude/skills/payment-handler-mcp/.env.example
  - .claude/skills/payment-handler-mcp/SKILL.md
tests:
  - manual: npm run inspect to verify 4 tools listed
  - manual: draft_payment with new recipient to verify new_recipient fraud flag
  - manual: list_scheduled_payments to verify pending payment listing
  - manual: cancel_pending_payment to verify file moved to Rejected/
---

## Prompt

Create an Agent Skill called "payment-handler-mcp" that manages payment workflows with strong security controls. Requirements: MCP server for payment operations, support bank transfer/PayPal/Stripe, mandatory HITL approval for ALL payments, fraud detection (velocity, anomaly, duplicate, new-recipient, daily limit), never store credentials in vault, 24h approval expiry, payment verification, graceful failure handling with retry, logging to Logs/payments.json, suspicious pattern alerts. 4 MCP tools: draft_payment, verify_payment_status, cancel_pending_payment, list_scheduled_payments. File structure: SKILL.md, mcp_server.js, payment_clients/ (bank_transfer.js, paypal_client.js, stripe_client.js), approval_validator.js, fraud_detection.js, package.json.

## Response snapshot

Created 9 files in `.claude/skills/payment-handler-mcp/`:

1. **fraud_detection.js** — Pure-logic FraudDetector with 5 checks: new_recipient (first-time payee), high_velocity (>3/hour), amount_anomaly (>2× average), daily_limit_exceeded ($5000 cap), possible_duplicate (10min window). Returns risk score 0-100 with weighted flags. Reads history from Logs/payments.json.

2. **approval_validator.js** — PaymentApprovalValidator wrapping social-poster-mcp's ApprovalHandler (composition). Creates APPROVAL_REQUIRED_payment_*.md with fraud analysis embedded. 24h hard expiry auto-rejects. Includes security checklist in markdown. listPendingPayments() for scheduled payment listing. cancelApproval() moves to Rejected/ with annotation.

3. **payment_clients/bank_transfer.js** — Configurable banking API client. initiateTransfer, checkStatus, cancelTransfer. Env vars: BANK_API_URL, BANK_API_KEY.

4. **payment_clients/paypal_client.js** — PayPal REST v2 Payouts API. client_credentials OAuth with in-memory token caching. createPayment, checkStatus, cancelPayment (cancels UNCLAIMED items). Sandbox mode default. Env: PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET.

5. **payment_clients/stripe_client.js** — Stripe Payment Intents with manual capture. createPayment (holds funds), capturePayment (finalizes), checkStatus, cancelPayment. Handles cents conversion. Env: STRIPE_SECRET_KEY.

6. **mcp_server.js** — 4 MCP tools. draft_payment: fraud detection → approval file → log. verify_payment_status: checks approval system then tries all providers. cancel_pending_payment: approval system then provider cancellation. list_scheduled_payments: reads pending payment approvals.

7. **package.json** — Minimal: @modelcontextprotocol/sdk + dotenv.

8. **.env.example** — All credentials as env vars with security note.

9. **SKILL.md** — Full docs with security principles, fraud detection table, risk scoring weights, approval workflow, architecture diagram, per-provider config.

## Outcome

- ✅ Impact: Complete secure payment MCP server with fraud detection and mandatory HITL approval
- 🧪 Tests: Manual verification via MCP Inspector; fraud detection testable with Logs/payments.json history
- 📁 Files: 9 files created in .claude/skills/payment-handler-mcp/
- 🔁 Next prompts: Configure credentials in .env, npm install, test draft_payment flow
- 🧠 Reflection: Fraud detection as a pre-approval filter is the key security innovation — human reviewers see flags before deciding. Composition over inheritance for ApprovalValidator keeps modules decoupled.

## Evaluation notes (flywheel)

- Failure modes observed: None — clean implementation with security-first design
- Graders run and results (PASS/FAIL): N/A — requires provider credentials for full integration test
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add webhook receiver for async payment status updates from providers
