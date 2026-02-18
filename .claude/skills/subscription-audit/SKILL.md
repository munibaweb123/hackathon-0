---
name: subscription-audit
description: Identifies and analyzes recurring expenses from the Obsidian vault. Detects subscriptions via pattern matching, flags waste, price increases, and duplicates, then generates audit reports with cancellation recommendations.
tools: []
tags:
  - finance
  - analytics
  - python
  - audit
  - subscriptions
---

# Subscription Audit

Standalone Python skill that scans vault transaction data to identify recurring subscriptions, flag issues (inactive services, price increases, duplicate functionality), and generate detailed audit reports with savings recommendations.

## Quick Start

```bash
# Using UV (recommended — auto-installs dependencies)
uv run subscription_audit.py --vault-path ../../obsidian-vault

# Using pip
pip install -r requirements.txt
python subscription_audit.py --vault-path ../../obsidian-vault
```

## What It Does

1. **Scans** `Accounting/` folders and `Logs/payments.json` for transaction history
2. **Identifies** subscriptions using a curated 44-vendor pattern database with fuzzy matching
3. **Detects** recurring charges (same vendor, similar amount ±5%, monthly/weekly/quarterly/annual)
4. **Checks** for usage signals in `completed/`, `Done/`, and `Logs/` folders
5. **Flags** issues:
   - No vault activity in 30+ days (potential waste)
   - Price increases (compared to previous charges and typical tier pricing)
   - Duplicate/overlapping subscriptions (e.g., multiple video streaming services)
6. **Calculates** total monthly subscription cost and category breakdown
7. **Generates** report at `Reports/Subscription_Audit_{date}.md`
8. **Recommends** cancellations with cost savings estimates
9. **Tracks** changes between audits via `Logs/subscription_audits.json`

## Architecture

```
subscription-audit/
├── subscription_audit.py          # Main UV-runnable script (PEP 723)
├── pattern_matcher.py             # Vendor normalization + fuzzy matching
├── subscription_database.json     # 44 vendors, 9 duplicate groups
├── templates/
│   └── audit_report_template.md   # Jinja2 report template
├── requirements.txt
└── SKILL.md
```

## Vault Data Sources

| Source | Purpose |
|--------|---------|
| `Logs/payments.json` | Payment transaction history |
| `Logs/accounting.json` | Accounting operation logs |
| `Accounting/expenses/*.md` | Expense records (frontmatter) |
| `Accounting/payments/*.md` | Payment records (frontmatter) |
| `Accounting/invoices/*.md` | Invoice/bill records |
| `completed/*.md` | Completed tasks (activity signals) |
| `Done/*.md` | Done items (activity signals) |
| `Logs/*.json` | All log files (activity signals) |

## Pattern Database

The `subscription_database.json` contains:

- **44 vendors** across 13 categories (entertainment, productivity, cloud, design, communication, security, finance, AI, developer, marketing, storage, education, other)
- **9 duplicate groups** (video streaming, music streaming, cloud storage, project management, communication, design, password manager, VPN, AI assistant)
- **Typical pricing tiers** for price increase detection

### Vendor Matching

The `PatternMatcher` normalizes vendor strings by:
1. Lowercasing
2. Stripping corporate suffixes (Inc, LLC, Ltd, Corp, etc.)
3. Stripping domain suffixes (.com, .io, .co, etc.)
4. Collapsing whitespace

Then matches via:
- Exact match (confidence: 1.0)
- Substring containment (confidence: 0.8+)
- Bigram similarity ratio (threshold: 0.65)

### Custom Patterns

Add vendor patterns at runtime:
```python
auditor = SubscriptionAuditor(vault_path="...")
auditor.matcher.add_custom_pattern(
    canonical="My SaaS Tool",
    patterns=["mysaas", "my saas tool", "mysaas.io"],
    category="productivity"
)
```

## Report Sections

1. **Summary** — active count, total monthly/annual cost, flagged issues, potential savings
2. **Active Subscriptions** — table with vendor, category, cost, frequency, last charge, status
3. **Category Breakdown** — spend per category with percentage
4. **Flagged Issues** — no activity, price increases, duplicates (each with details)
5. **Cancellation Recommendations** — prioritized by savings with reasons
6. **Changes Since Last Audit** — new, removed, and price-changed subscriptions

## CLI Options

```
--vault-path PATH   Path to Obsidian vault (default: ./obsidian-vault)
--date DATE         Audit date as YYYY-MM-DD (default: today)
--verbose, -v       Enable debug logging
```

## Output

Reports saved to:
```
obsidian-vault/Reports/Subscription_Audit_2026-02-17.md
```

Audit history appended to:
```
obsidian-vault/Logs/subscription_audits.json
```

## Frequency Detection

Recurring charges are identified by analyzing payment intervals:

| Frequency | Interval Range |
|-----------|---------------|
| Weekly | 5-10 days |
| Biweekly | 12-18 days |
| Monthly | 25-35 days |
| Quarterly | 80-100 days |
| Annual | 340-400 days |

Minimum 2 occurrences required. Amounts grouped with 5% tolerance.

## Dependencies

- Python 3.10+
- `jinja2` — template rendering
- `python-dotenv` — .env loading

All declared in PEP 723 script header for automatic UV resolution. No fuzzy matching libraries — uses built-in bigram similarity.
