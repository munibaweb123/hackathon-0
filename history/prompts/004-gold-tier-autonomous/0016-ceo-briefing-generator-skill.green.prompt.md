---
id: "0016"
title: CEO Briefing Generator Agent Skill
stage: green
date: 2026-02-16
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: developer
command: create-skill
labels: ["ceo-briefing", "python", "analytics", "reporting", "vault-reader"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/ceo-briefing-generator/SKILL.md
  - .claude/skills/ceo-briefing-generator/briefing_generator.py
  - .claude/skills/ceo-briefing-generator/analyzers/__init__.py
  - .claude/skills/ceo-briefing-generator/analyzers/revenue_analyzer.py
  - .claude/skills/ceo-briefing-generator/analyzers/task_analyzer.py
  - .claude/skills/ceo-briefing-generator/analyzers/subscription_analyzer.py
  - .claude/skills/ceo-briefing-generator/templates/briefing_template.md
  - .claude/skills/ceo-briefing-generator/requirements.txt
tests:
  - "uv run briefing_generator.py --vault-path ../../../obsidian-vault --once"
---

## Prompt

Create an Agent Skill called 'ceo-briefing-generator' that creates comprehensive Monday morning business reports.

Requirements:
- Sunday 11 PM cron generation for Monday morning readiness
- Read Business_Goals.md, Done/, Accounting/ from vault
- Revenue analysis (MTD, WoW, forecast via simple moving average)
- Task velocity trends and bottleneck detection
- Subscription waste detection (recurring payments with no activity)
- ASCII velocity charts in briefing output
- Actionable AI recommendations (3-5 bullets)
- Python UV-runnable with PEP 723 headers
- Jinja2 template for clean data/presentation separation
- Output to Briefings/{date}_Monday_Briefing.md

## Response snapshot

Created 8 files in `.claude/skills/ceo-briefing-generator/`:

1. **briefing_generator.py** — Main UV-runnable Python script (PEP 723 headers: jinja2, python-dotenv, pyyaml). BriefingGenerator class orchestrates 3 analyzers, loads business goals, generates executive summary and recommendations, renders via Jinja2, saves to vault.

2. **analyzers/revenue_analyzer.py** — RevenueAnalyzer reads Logs/payments.json, Logs/accounting.json, Accounting/invoices/*.md, Accounting/expenses/*.md. Produces: revenue_this_week, revenue_mtd, expenses, net_income, budget_burn_rate, top_revenue_sources (top 3), overdue_invoices, wow_change, forecast_next_week (4-week SMA).

3. **analyzers/task_analyzer.py** — TaskAnalyzer reads completed/, Done/, pending-approval/. Produces: tasks_completed_this_week, tasks_pending, velocity_trend (5 weeks), velocity_change, bottlenecks (pending >48h), completion_rate, top_categories.

4. **analyzers/subscription_analyzer.py** — SubscriptionAnalyzer detects recurring payments via amount grouping (5% tolerance) and interval analysis (weekly/biweekly/monthly/quarterly). Waste detection cross-references subscriptions against vault activity in last 30 days. Predicts upcoming renewals.

5. **templates/briefing_template.md** — Jinja2 template with Executive Summary, Revenue table, Velocity chart, Subscription table, Pending Actions, AI Recommendations, Business Goals sections.

6. **analyzers/__init__.py** — Re-exports all 3 analyzers.
7. **requirements.txt** — jinja2, python-dotenv, pyyaml.
8. **SKILL.md** — Full documentation with architecture, vault data sources, CLI options, scheduling.

Key design: Python UV script (not MCP server) — one-shot generation with zero API dependencies. Reads vault directly. CLI: `--vault-path`, `--week-start`, `--once`, `--verbose`.

## Outcome

- ✅ Impact: Complete CEO briefing generator with 3 specialized analyzers, Jinja2 templating, and direct vault reads
- 🧪 Tests: `uv run briefing_generator.py --vault-path ../../../obsidian-vault --once`
- 📁 Files: 8 files created in .claude/skills/ceo-briefing-generator/
- 🔁 Next prompts: None — all planned skills complete
- 🧠 Reflection: Python UV script pattern (matching gmail-watcher) is cleaner than MCP for one-shot generation tasks; separate analyzer modules keep each data domain testable independently

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Manual verification PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add unit tests for individual analyzers with mock vault data
