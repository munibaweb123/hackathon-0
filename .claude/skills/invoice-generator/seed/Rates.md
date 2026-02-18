---
invoice_prefix: "INV"
default_tax_rate: 0.0
default_currency: "USD"
rates:
  - name: "Web Development"
    type: hourly
    rate: 150.00
    currency: USD
    description: "Full-stack web development services"
  - name: "UI/UX Design"
    type: hourly
    rate: 125.00
    currency: USD
    description: "User interface and experience design"
  - name: "Consulting"
    type: hourly
    rate: 200.00
    currency: USD
    description: "Strategic technology consulting"
  - name: "Monthly Retainer - Basic"
    type: fixed
    rate: 2500.00
    currency: USD
    description: "Basic monthly support retainer (20 hrs included)"
    recurring: monthly
  - name: "Monthly Retainer - Premium"
    type: fixed
    rate: 5000.00
    currency: USD
    description: "Premium monthly support retainer (50 hrs included)"
    recurring: monthly
  - name: "Project Setup Fee"
    type: fixed
    rate: 500.00
    currency: USD
    description: "One-time project onboarding and setup"
recurring_clients: []
---

# Service Rates

This file defines billing rates used by the invoice generator.

## How to Configure

1. Edit the `rates` array above to match your service offerings
2. Set `default_tax_rate` (0.0 = no tax, 0.08 = 8%, etc.)
3. Set `invoice_prefix` for invoice numbering (default: "INV")
4. Add recurring clients to `recurring_clients` for automatic monthly invoicing

## Rate Types

- **hourly**: Billed per hour (quantity = hours worked)
- **fixed**: Flat fee per deliverable or period

## Recurring Invoices

Add `recurring: monthly` to any rate entry to enable automatic recurring invoicing.
Add clients to `recurring_clients`:

```yaml
recurring_clients:
  - customer: "ACME Corp"
    email: "billing@acme.com"
    rate_name: "Monthly Retainer - Basic"
    start_date: "2026-01-01"
```
