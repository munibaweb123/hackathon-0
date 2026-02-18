---
company_name: "Your Company Name"
tagline: "Professional Services"
address: |
  123 Business Street
  Suite 100
  City, State 12345
email: "billing@yourcompany.com"
phone: "+1 (555) 123-4567"
website: "https://yourcompany.com"
tax_id: "XX-XXXXXXX"
bank_name: "First National Bank"
bank_account: "XXXX-XXXX-XXXX"
bank_routing: "XXX-XXX-XXX"
logo_path: "config/logo.png"
default_payment_terms: "Net 30"
default_currency: "USD"
---

# Company Information

This file contains company branding and billing details used by the invoice generator.

## How to Configure

1. Replace all placeholder values above with your real company information
2. Place your company logo at `config/logo.png` in the vault (optional)
3. Set your tax ID for invoice compliance
4. Configure bank details for payment instructions on invoices

## Fields

- **company_name**: Your legal business name (appears on invoice header)
- **tagline**: Short description (appears below company name)
- **address**: Full mailing address (multi-line)
- **email**: Billing contact email
- **phone**: Business phone number
- **website**: Company website URL
- **tax_id**: Tax identification number (EIN, VAT, etc.)
- **bank_name/account/routing**: Payment details shown on invoice footer
- **logo_path**: Path to logo image relative to vault root (PNG/JPG, recommended 200x80px)
- **default_payment_terms**: Default terms shown on invoices (e.g., "Net 30", "Due on Receipt")
- **default_currency**: Three-letter currency code (USD, EUR, GBP, etc.)
