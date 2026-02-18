---
name: ceo-briefing-generator
description: Generates comprehensive Monday morning CEO briefings by analyzing Obsidian vault data — revenue, task velocity, subscription waste, and business goals
tools: []
tags:
  - reporting
  - analytics
  - python
  - briefing
---

# CEO Briefing Generator

Standalone Python skill that creates comprehensive weekly business reports by reading the Obsidian vault directly. Zero external API dependencies — works entirely offline with vault data.

## Quick Start

```bash
# Using UV (recommended — auto-installs dependencies)
uv run briefing_generator.py --vault-path ../../obsidian-vault --once

# Using pip
pip install -r requirements.txt
python briefing_generator.py --vault-path ../../obsidian-vault --once
```

## What It Generates

A structured Monday morning briefing saved to `Briefings/{date}_Monday_Briefing.md` containing:

1. **Executive Summary** — 1-paragraph auto-generated overview
2. **Revenue & Financial Health** — weekly revenue, MTD, WoW change, forecast, overdue invoices, budget burn rate
3. **Task Velocity & Productivity** — completion stats, velocity trend (5-week chart), bottlenecks, top categories
4. **Subscription & Recurring Costs** — detected subscriptions, waste alerts, upcoming renewals, cost trend
5. **Pending Actions** — items stuck in approval >48 hours
6. **AI Recommendations** — 3-5 actionable bullets based on analysis
7. **Business Goals Progress** — from `config/Business_Goals.md`

## Architecture

```
ceo-briefing-generator/
├── briefing_generator.py          # Main UV-runnable script (PEP 723)
├── analyzers/
│   ├── __init__.py
│   ├── revenue_analyzer.py        # Logs/payments.json, Accounting/*
│   ├── task_analyzer.py           # completed/, Done/, pending-approval/
│   └── subscription_analyzer.py   # Recurring payment detection + waste
├── templates/
│   └── briefing_template.md       # Jinja2 template
├── requirements.txt
└── SKILL.md
```

## Vault Data Sources

| Source | Read By | Purpose |
|--------|---------|---------|
| `Logs/payments.json` | RevenueAnalyzer, SubscriptionAnalyzer | Payment history, revenue calculation |
| `Logs/accounting.json` | RevenueAnalyzer | Accounting operation logs |
| `Accounting/invoices/*.md` | RevenueAnalyzer | Invoice status, overdue detection |
| `Accounting/expenses/*.md` | RevenueAnalyzer, SubscriptionAnalyzer | Expense tracking, subscription detection |
| `completed/*.md` | TaskAnalyzer, SubscriptionAnalyzer | Completed task records |
| `Done/*.md` | TaskAnalyzer | Alternative completion folder |
| `pending-approval/*.md` | TaskAnalyzer | Pending items, bottleneck detection |
| `config/Business_Goals.md` | BriefingGenerator | Goal progress tracking |

## Analyzers

### RevenueAnalyzer
- Weekly/MTD revenue from payment logs
- Week-over-week change percentage
- Budget burn rate projection
- Top 3 revenue sources
- Overdue invoice detection
- 4-week simple moving average forecast

### TaskAnalyzer
- Weekly task completion count
- 5-week velocity trend with ASCII chart
- Velocity change percentage
- Bottleneck detection (pending >48h)
- Completion rate
- Top task categories

### SubscriptionAnalyzer
- Automatic recurring payment detection (weekly/biweekly/monthly/quarterly)
- Amount similarity grouping (5% tolerance)
- Waste detection — flags subscriptions with no vault activity in 30 days
- Upcoming renewal predictions
- 3-month cost trend

## CLI Options

```
--vault-path PATH   Path to Obsidian vault (default: ./obsidian-vault)
--week-start DATE   Monday date as YYYY-MM-DD (default: current week)
--once              Generate and exit (default behavior)
--verbose, -v       Enable debug logging
```

## Scheduling

The existing `config/schedules.yaml` has a `ceo_briefing` entry at `0 8 * * 0` (8 AM Sundays). To use with cron directly:

```cron
0 23 * * 0 cd /path/to/skills/ceo-briefing-generator && uv run briefing_generator.py --vault-path /path/to/obsidian-vault --once
```

## Output

Briefings are saved to:
```
obsidian-vault/Briefings/2026-02-16_Monday_Briefing.md
```

Generation logs appended to:
```
obsidian-vault/Logs/briefings.json
```

## Dependencies

- Python 3.10+
- `jinja2` — template rendering
- `python-dotenv` — .env loading
- `pyyaml` — YAML parsing

All declared in PEP 723 script header for automatic UV resolution.
