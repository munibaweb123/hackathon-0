---
name: invoice-generator
description: Creates professional invoices automatically with PDF generation, HITL approval, overdue reminders, recurring support, and email delivery integration.
tools: []
tags:
  - finance
  - invoicing
  - python
  - pdf
  - approval
---

# Invoice Generator

Standalone Python skill that automates the full invoice lifecycle: detect need, calculate amounts, generate PDF, get human approval, send via email, track status, and send overdue reminders.

## Quick Start

```bash
# Using UV (recommended — auto-installs reportlab, jinja2, pyyaml)
uv run invoice_generator.py --vault-path ../../obsidian-vault \
  --generate --customer "ACME Corp" \
  --items '[{"description":"Web Development","quantity":10,"rate":150}]'

# Using pip
pip install -r requirements.txt
python invoice_generator.py --vault-path ../../obsidian-vault --generate ...
```

On first run, seed config files (`Company_Info.md`, `Rates.md`) are copied to `vault/config/` if not present.

## Invoice Workflow

```
1. TRIGGER  → detect_needs() finds request in Needs_Action/
              OR generate_recurring() finds due monthly retainer
              OR CLI --generate with explicit params

2. CALCULATE → Look up Rates.md, compute subtotal + tax + total

3. GENERATE  → reportlab creates Accounting/invoices/INV-{N}.pdf
               + copies PDF to Attachments/ for email delivery

4. APPROVAL  → Creates pending-approval/APPROVAL_REQUIRED_invoice_{N}.md
               Human moves to Approved/ or Rejected/

5. SEND      → check_approvals() detects → creates email action file
               for email-sender-mcp with PDF attachment

6. LOG       → Accounting/invoices/INV-{N}.md status → "sent"
               Logs/invoices.json appended

7. TRACK     → reminder_scheduler checks overdue, creates
               Needs_Action/REMINDER_OVERDUE_{N}_{level}.md
```

## Architecture

```
invoice-generator/
├── invoice_generator.py           # Main UV-runnable script (orchestrator)
├── pdf_creator.py                 # reportlab PDF generation
├── invoice_template.html          # HTML email body template (Jinja2)
├── reminder_scheduler.py          # Overdue detection + reminder creation
├── seed/
│   ├── Company_Info.md            # Company branding config (copied to vault)
│   └── Rates.md                   # Service rates config (copied to vault)
├── requirements.txt
└── SKILL.md
```

## CLI Modes

```
--generate              Create a new invoice
  --customer NAME       Customer name
  --customer-email EMAIL Customer email for delivery
  --items JSON          Line items: [{"description":"...","quantity":N,"rate":N}]
  --rate-names LIST     Comma-separated rate names from Rates.md
  --quantities LIST     Comma-separated quantities (with --rate-names)
  --due-days N          Days until due (default: 30)
  --notes TEXT          Invoice notes

--recurring             Process recurring invoices from Rates.md
--detect                Scan Needs_Action/ for invoice requests
--check-approvals       Process approved invoices (trigger email send)
--reminders             Check overdue invoices and create reminders
--status INV-NUM STATUS Update invoice status (draft|approved|sent|paid|overdue)

--vault-path PATH       Obsidian vault path (default: ./obsidian-vault)
--verbose, -v           Enable debug logging
```

## Examples

```bash
# Generate from explicit line items
uv run invoice_generator.py --vault-path ../../obsidian-vault \
  --generate --customer "ACME Corp" --customer-email "billing@acme.com" \
  --items '[{"description":"Web Development","quantity":10,"rate":150},{"description":"Design","quantity":5,"rate":125}]'

# Generate from predefined rates
uv run invoice_generator.py --vault-path ../../obsidian-vault \
  --generate --customer "Beta Inc" \
  --rate-names "Web Development,Consulting" --quantities "8,3"

# Process recurring monthly invoices
uv run invoice_generator.py --vault-path ../../obsidian-vault --recurring

# Check for approved invoices and prepare email sends
uv run invoice_generator.py --vault-path ../../obsidian-vault --check-approvals

# Generate overdue reminders
uv run invoice_generator.py --vault-path ../../obsidian-vault --reminders

# Mark invoice as paid
uv run invoice_generator.py --vault-path ../../obsidian-vault --status INV-0001 paid
```

## Configuration

### Company Info (`config/Company_Info.md`)

YAML frontmatter with: `company_name`, `tagline`, `address`, `email`, `phone`, `website`, `tax_id`, `bank_name`, `bank_account`, `bank_routing`, `logo_path`, `default_payment_terms`, `default_currency`.

### Rates (`config/Rates.md`)

YAML frontmatter with:
- `invoice_prefix` — Invoice number prefix (default: "INV")
- `default_tax_rate` — Tax rate as decimal (0.0 = no tax, 0.08 = 8%)
- `rates` — Array of `{name, type, rate, currency, description, recurring}`
- `recurring_clients` — Array of `{customer, email, rate_name, start_date}`

## Vault Data Sources

| Source | Read/Write | Purpose |
|--------|------------|---------|
| `config/Company_Info.md` | Read | Company branding for invoices |
| `config/Rates.md` | Read | Service rates and recurring config |
| `Accounting/invoices/*.md` | Write | Invoice records (metadata) |
| `Accounting/invoices/*.pdf` | Write | Generated PDF invoices |
| `Attachments/*.pdf` | Write | PDF copy for email-sender-mcp |
| `pending-approval/` | Write | HITL approval requests |
| `Approved/` | Read | Approved invoice files |
| `Needs_Action/` | Read/Write | Invoice requests + overdue reminders |
| `Logs/invoices.json` | Write | Invoice event log |
| `Logs/invoice_counter.json` | Read/Write | Auto-incrementing invoice number |
| `Logs/invoice_reminders.json` | Read/Write | Reminder dedup tracking |

## Overdue Reminders

The `ReminderScheduler` creates escalating reminders based on days overdue:

| Days Overdue | Level | Tone |
|-------------|-------|------|
| 1-7 | Gentle | Friendly reminder |
| 8-14 | Firm | Payment request |
| 15-30 | Final | Final notice |
| 30+ | Escalation | Immediate action required |

Each reminder includes a suggested email template and is deduplicated via `Logs/invoice_reminders.json`.

## PDF Features

- Company logo support (PNG/JPG)
- Professional table layout with alternating row colors
- Branded header with company colors
- Line items with description, qty, rate, amount
- Subtotal, tax, and total calculation
- Payment instructions section
- Letter-sized (8.5" x 11")

## Dependencies

- Python 3.10+
- `reportlab` — PDF generation
- `jinja2` — HTML email template rendering
- `python-dotenv` — .env loading
- `pyyaml` — YAML frontmatter parsing (complex structures like arrays)

All declared in PEP 723 script header for automatic UV resolution.
