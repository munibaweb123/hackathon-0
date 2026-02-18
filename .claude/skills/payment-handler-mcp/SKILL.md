---
name: payment-handler-mcp
description: Secure MCP server for payment workflows with mandatory HITL approval, fraud detection, and support for bank transfer, PayPal, and Stripe.
---

# Payment Handler MCP Server

A security-first MCP server for payment operations. **Every payment requires human approval** — no exceptions. Built-in fraud detection flags suspicious patterns before the human reviewer sees the approval request.

## Quick Start

```bash
cd .claude/skills/payment-handler-mcp
npm install

# Configure credentials (env vars only — never in vault)
cp .env.example .env
# Edit .env with your Stripe/PayPal/Bank credentials

# Test with MCP Inspector
npm run inspect
```

## Security Principles

1. **ALL payments require HITL approval** — no auto-execute, regardless of amount
2. **Credentials never stored in vault** — env vars or secure credential manager only
3. **Fraud detection runs before approval** — flags embedded in the approval file
4. **24-hour hard expiry** — stale approvals auto-reject
5. **New recipients always flagged** — first-time payees trigger extra scrutiny
6. **Full audit trail** — every attempt logged to `Logs/payments.json`

## MCP Tools

### 1. `draft_payment` (HITL — always)

Draft a payment for human approval. Runs fraud detection first.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `recipient` | string | yes | Payee name or identifier |
| `amount` | number | yes | Amount in major currency units (e.g., 150.00) |
| `method` | string | yes | `bank_transfer`, `paypal`, or `stripe` |
| `reference` | string | no | Invoice or reference number |
| `category` | string | no | Category (vendor, salary, subscription) |
| `currency` | string | no | Currency code (default: USD) |

**Returns:**
```json
{
  "success": true,
  "status": "pending_approval",
  "approvalId": "a1b2c3d4",
  "approvalFile": "APPROVAL_REQUIRED_payment_a1b2c3d4.md",
  "riskLevel": "high",
  "riskScore": 25,
  "fraudFlags": ["new_recipient"],
  "safe": false,
  "message": "Payment drafted with 1 security flag(s). Review carefully before approving."
}
```

### 2. `verify_payment_status` (read-only)

Check payment status by approval ID or provider transaction ID.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `payment_id` | string | yes | Approval ID or provider transaction ID |
| `method` | string | no | Narrow search to specific provider |

**Returns:** Approval status + provider status if applicable.

### 3. `cancel_pending_payment`

Cancel a pending payment. Checks approval system first, then providers.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `payment_id` | string | yes | Approval ID or provider transaction ID |

**Returns:** `{ cancelled: boolean, message: string }`

### 4. `list_scheduled_payments` (read-only)

List all pending payment approvals.

**Returns:**
```json
{
  "count": 2,
  "payments": [
    {
      "approvalId": "a1b2c3d4",
      "recipient": "ACME Corp",
      "amount": "150",
      "method": "stripe",
      "riskLevel": "high",
      "expiresIn": "23h 45m"
    }
  ]
}
```

## Fraud Detection

The `FraudDetector` runs 5 checks before every payment draft:

| Check | Flag | Trigger |
|-------|------|---------|
| New recipient | `new_recipient` | First-time payee (no prior successful payments) |
| Velocity | `high_velocity` | >3 payments in 1 hour to same recipient |
| Amount anomaly | `amount_anomaly` | Payment > 2× historical average for this recipient |
| Daily limit | `daily_limit_exceeded` | Cumulative today > $5,000 (configurable) |
| Duplicate | `possible_duplicate` | Same recipient + amount + reference within 10 minutes |

### Risk Scoring

Each flag adds to the risk score (0-100):

| Flag | Weight |
|------|--------|
| `possible_duplicate` | 35 |
| `high_velocity` | 30 |
| `new_recipient` | 25 |
| `amount_anomaly` | 20 |
| `daily_limit_exceeded` | 15 |

Amount-based bonus: +5 (>$1K), +10 (>$5K), +15 (>$10K).

## HITL Approval Workflow

```
1. Claude calls draft_payment
2. FraudDetector.analyze() → flags + risk score
3. PaymentApprovalValidator creates approval file:
   → pending-approval/APPROVAL_REQUIRED_payment_<8char_id>.md
4. Approval file includes:
   - Transaction details table
   - Fraud analysis with flags
   - Security checklist
   - Decision instructions
5. Human reviews and moves file:
   → Approved/ (execute payment)
   → Rejected/ (cancel)
6. After 24 hours: auto-expires to Rejected/
```

### Approval File Example

```markdown
# 🔴 Payment Approval Required

## Transaction Details

| Field | Value |
|-------|-------|
| **Recipient** | ACME Corp |
| **Amount** | USD 2500.00 |
| **Method** | Stripe |
| **Risk Score** | 55/100 |

## Security Analysis

**⚠️ 2 flag(s) detected:**

- **new_recipient**: First-time payment to this recipient.
- **amount_anomaly**: Amount 2500 is 3.2× the average (781.25) for this recipient.

## ⚠️ Security Checklist

- [ ] Recipient identity verified
- [ ] Amount matches expected value
- [ ] Payment method is correct
- [ ] Reference matches a known invoice/contract
- [ ] No credential data is stored in this file
```

## Architecture

```
MCP Client (Claude Desktop / Inspector)
       │  stdio
       ▼
  mcp_server.js (4 tools)
       │
       ├──▶ fraud_detection.js (analyze before approval)
       │         └──▶ Logs/payments.json (history for pattern detection)
       │
       ├──▶ approval_validator.js (HITL + 24h expiry)
       │         ├──▶ pending-approval/ → Approved/ → Rejected/
       │         └──▶ ../social-poster-mcp/approval_handler.js (base)
       │
       └──▶ payment_clients/
             ├── bank_transfer.js  → Banking API
             ├── paypal_client.js  → PayPal REST v2
             └── stripe_client.js  → Stripe Payment Intents
```

## Payment Methods

### Bank Transfer

Connects to a configurable banking API.

| Env Var | Description |
|---------|-------------|
| `BANK_API_URL` | Banking API base URL |
| `BANK_API_KEY` | API key |

### PayPal

Uses PayPal Payouts API v2 with client_credentials OAuth.

| Env Var | Description |
|---------|-------------|
| `PAYPAL_CLIENT_ID` | PayPal app client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal app client secret |
| `PAYPAL_SANDBOX` | `true` (default) or `false` for production |

Access tokens are cached in memory only — never written to disk.

### Stripe

Uses Stripe Payment Intents with manual capture mode.

| Env Var | Description |
|---------|-------------|
| `STRIPE_SECRET_KEY` | `sk_test_*` or `sk_live_*` |

Amount handling: Stripe uses cents internally; the client converts automatically.

## Claude Desktop Integration

```json
{
  "mcpServers": {
    "payment-handler": {
      "command": "node",
      "args": ["/path/to/.claude/skills/payment-handler-mcp/mcp_server.js"],
      "env": {
        "VAULT_PATH": "/path/to/obsidian-vault",
        "STRIPE_SECRET_KEY": "sk_test_...",
        "PAYPAL_CLIENT_ID": "...",
        "PAYPAL_CLIENT_SECRET": "...",
        "PAYPAL_SANDBOX": "true",
        "PAYMENT_DAILY_LIMIT": "5000"
      }
    }
  }
}
```

## File Structure

```
.claude/skills/payment-handler-mcp/
├── SKILL.md                  # This documentation
├── mcp_server.js             # MCP server (stdio, 4 tools)
├── fraud_detection.js        # 5-check fraud analysis
├── approval_validator.js     # Payment-specific HITL handler
├── payment_clients/
│   ├── bank_transfer.js      # Configurable banking API
│   ├── paypal_client.js      # PayPal REST API v2
│   └── stripe_client.js      # Stripe Payment Intents
├── package.json              # Dependencies (minimal)
└── .env.example              # Credential template
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing credentials | Draft still works (no API needed); verify/cancel fails gracefully |
| Fraud flags detected | Payment still drafted but flagged; human decides |
| Approval expired (24h) | Auto-moved to Rejected/ |
| Provider API error | Retry 3× with exponential backoff |
| Duplicate payment | Flagged in fraud analysis; human decides |
| Cancel after execution | Attempts provider-level cancellation |

## Credential Security

- Credentials load from **environment variables only**
- PayPal tokens cached **in memory only** (never written to disk)
- Vault files **never contain** API keys, secrets, or tokens
- Approval files contain **method names only** (e.g., "stripe"), never credentials
- `.env` file should be in `.gitignore` (never committed)
