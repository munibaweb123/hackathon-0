---
name: odoo-accounting-mcp
description: MCP server for Odoo Community Edition (v19+) accounting operations. Exposes invoice, payment, expense, and balance tools with HITL approval for financial operations.
---

# Odoo Accounting MCP Server

An MCP (Model Context Protocol) server that integrates with Odoo Community Edition (v19+) for accounting operations. Financial write operations require Human-in-the-Loop approval; read-only queries execute directly.

## Quick Start

```bash
cd .claude/skills/odoo-accounting-mcp
npm install

# Copy and configure Odoo connection
cp odoo_config.example.json odoo_config.json
# Edit odoo_config.json with your Odoo credentials

# Test with MCP Inspector
npm run inspect

# Or run directly
node mcp_server.js
```

## Prerequisites

1. **Node.js 18+** (uses native `fetch()`)
2. **Odoo Community Edition v19+** running at `http://localhost:8069`
3. **Odoo database** with Accounting module installed
4. **Admin credentials** (or a user with Accounting access rights)

### Odoo Setup

1. Install Odoo CE: `docker run -d -p 8069:8069 --name odoo odoo:19`
2. Create a database via the Odoo web UI
3. Install the **Accounting** module (Invoicing app)
4. Configure at least one **Bank Journal** in Accounting → Configuration → Journals

## MCP Tools

### 1. `create_invoice` (HITL)

Create a customer invoice. Requires approval.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `partner_name` | string | yes | Customer name (auto-resolved or created) |
| `line_items` | array | yes | Array of `{ description, quantity, unit_price }` |
| `due_date` | string | no | Due date (YYYY-MM-DD) |
| `currency` | string | no | Currency code (USD, EUR, PKR). Defaults to company currency. |

**Returns:** `{ approvalId, approvalFile, estimatedTotal, status: "pending_approval" }`

### 2. `record_payment` (HITL)

Record a payment against an invoice. Requires approval.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_id` | number | yes | Odoo invoice ID |
| `amount` | number | yes | Payment amount |
| `payment_date` | string | no | Date (YYYY-MM-DD). Defaults to today. |
| `method` | string | no | `bank`, `cash`, or `check`. Default: `bank`. |

**Returns:** `{ approvalId, approvalFile, status: "pending_approval" }`

### 3. `create_expense` (HITL)

Log an expense. Requires approval.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | yes | Expense category (e.g., Travel, Office Supplies) |
| `amount` | number | yes | Expense amount |
| `description` | string | yes | Expense description |
| `date` | string | no | Date (YYYY-MM-DD). Defaults to today. |

**Returns:** `{ approvalId, approvalFile, status: "pending_approval" }`

### 4. `get_account_balance` (read-only)

Get balance for an account type. No approval needed.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_type` | string | yes | `receivable`, `payable`, `bank`, or `cash` |

**Returns:** `{ accountType, balance, accounts: [{ id, code, name, balance }] }`

### 5. `list_unpaid_invoices` (read-only)

List unpaid/partially paid customer invoices. No approval needed.

**Returns:** `{ count, invoices: [{ id, name, partnerName, amountTotal, amountResidual, dueDate }] }`

### 6. `create_partner` (HITL)

Create a customer/vendor record. Requires approval.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Partner name |
| `email` | string | no | Email address |
| `phone` | string | no | Phone number |
| `address` | string | no | Full address |

**Returns:** `{ approvalId, approvalFile, status: "pending_approval" }`

## HITL Approval Workflow

Financial operations follow this flow:

```
1. Claude calls create_invoice / record_payment / create_expense / create_partner
2. Approval file created in vault pending-approval/
   → APPROVAL_REQUIRED_odoo_<8char_id>.md
3. Human reviews the proposed operation in the file
4. Human moves file to Approved/ (or Rejected/)
5. Approval watcher detects and triggers execution in Odoo
```

### Risk Levels

| Operation | Risk Level |
|-----------|------------|
| `create_invoice` | High (financial commitment) |
| `record_payment` | High (money movement) |
| `create_expense` | Medium (internal record) |
| `create_partner` | Medium (contact creation) |
| `get_account_balance` | None (read-only) |
| `list_unpaid_invoices` | None (read-only) |

## Architecture

```
MCP Client (Claude Desktop / Inspector)
       │  stdio
       ▼
  mcp_server.js (6 tools)
       │
       ├──▶ approval_handler.js (HITL — reused from social-poster-mcp)
       │         └──▶ vault/pending-approval/ → Approved/ → Rejected/
       │
       ├──▶ odoo_client.js (JSON-RPC 2.0)
       │         └──▶ Odoo CE @ http://localhost:8069/jsonrpc
       │
       ├──▶ invoice_generator.js (invoice/payment/expense/balance logic)
       │         └──▶ vault/Accounting/{invoices,payments,expenses}/
       │
       └──▶ vault/Logs/accounting.json (audit log)
```

## Odoo JSON-RPC Protocol

All Odoo communication uses JSON-RPC 2.0 via `POST /jsonrpc`:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "id": 1,
  "params": {
    "service": "object",
    "method": "execute_kw",
    "args": ["db", uid, "password", "account.move", "search_read", [[]], {"fields": ["name"]}]
  }
}
```

Authentication: `service: "common"`, `method: "login"` → returns `uid`.

## Configuration

### Option 1: JSON config file (recommended)

Copy and edit:
```bash
cp odoo_config.example.json odoo_config.json
```

```json
{
  "url": "http://localhost:8069",
  "db": "mycompany",
  "username": "admin",
  "password": "admin"
}
```

### Option 2: Environment variables

```bash
ODOO_URL=http://localhost:8069
ODOO_DB=mycompany
ODOO_USERNAME=admin
ODOO_PASSWORD=admin
VAULT_PATH=../../obsidian-vault
```

### Option 3: Claude Desktop config

```json
{
  "mcpServers": {
    "odoo-accounting": {
      "command": "node",
      "args": ["/path/to/.claude/skills/odoo-accounting-mcp/mcp_server.js"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "mycompany",
        "ODOO_USERNAME": "admin",
        "ODOO_PASSWORD": "admin",
        "VAULT_PATH": "/path/to/obsidian-vault"
      }
    }
  }
}
```

## Vault Folder Structure

The skill creates and uses these vault folders:

```
obsidian-vault/
├── Accounting/
│   ├── invoices/    # Invoice PDFs downloaded from Odoo
│   ├── payments/    # Payment record markdown files
│   └── expenses/    # Expense record markdown files
├── pending-approval/  # HITL approval requests
├── Approved/          # Human-approved operations
├── Rejected/          # Human-rejected operations
└── Logs/
    └── accounting.json  # Full audit trail
```

## Multi-Currency Support

Pass `currency` to `create_invoice` to use non-default currencies:

```json
{ "partner_name": "ACME Corp", "line_items": [...], "currency": "USD" }
```

The currency must exist and be activated in Odoo (Accounting → Configuration → Currencies).

## Action Logging

Every operation is logged to `vault/Logs/accounting.json`:

```json
[
  {
    "timestamp": "2026-02-15T14:00:00.000Z",
    "service": "odoo",
    "action": "create_invoice",
    "invoiceId": 42,
    "invoiceName": "INV/2026/0001",
    "partnerId": 15,
    "partnerName": "ACME Corp",
    "total": 1500.00
  }
]
```

## File Structure

```
.claude/skills/odoo-accounting-mcp/
├── SKILL.md                  # This documentation
├── mcp_server.js             # MCP server (stdio, 6 tools)
├── odoo_client.js            # Odoo JSON-RPC 2.0 wrapper
├── invoice_generator.js      # Invoice/payment/expense/balance logic
├── package.json              # Dependencies (minimal)
└── odoo_config.example.json  # Connection config template
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Odoo not reachable | Retry 3× with backoff; clear error message |
| Auth failed | Error with credential check instructions |
| Invoice not found | Error with the invalid invoice ID |
| No bank journal | Error with Odoo setup instructions |
| Invalid currency | Silently falls back to company default |
| Missing Accounting module | Odoo RPC error surfaced to user |

## Troubleshooting

1. **"ECONNREFUSED"** — Odoo is not running at the configured URL
2. **"Authentication failed"** — Check db name, username, password
3. **"RPC error: account.move"** — Accounting module may not be installed
4. **"No bank journal found"** — Configure journals in Odoo → Accounting → Configuration → Journals
