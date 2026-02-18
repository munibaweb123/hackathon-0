---
id: "0017"
title: Subscription Audit Agent Skill
stage: green
date: 2026-02-17
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: developer
command: create-skill
labels: ["subscription", "audit", "python", "finance", "pattern-matching"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/subscription-audit/SKILL.md
  - .claude/skills/subscription-audit/subscription_audit.py
  - .claude/skills/subscription-audit/pattern_matcher.py
  - .claude/skills/subscription-audit/subscription_database.json
  - .claude/skills/subscription-audit/templates/audit_report_template.md
  - .claude/skills/subscription-audit/requirements.txt
tests:
  - "uv run subscription_audit.py --vault-path ../../../obsidian-vault"
---

## Prompt

Create an Agent Skill called "subscription-audit" that identifies and analyzes recurring expenses.

Requirements:
- Scan /Accounting/ folder for transaction history
- Identify subscriptions using pattern matching (e.g., "Netflix", "Notion", "Adobe")
- Detect recurring charges (same vendor, similar amount, monthly/annual)
- Check for usage signals (last login, activity logs if available)
- Flag subscriptions with: no activity in 30+ days, price increases, duplicates
- Calculate total monthly subscription cost
- Generate report: /Reports/Subscription_Audit_{date}.md
- Suggest cancellations with cost savings estimate
- Track subscription changes over time

Pattern database:
- Maintain list of common subscription vendors
- Detect variations (Netflix.com, NETFLIX, Netflix Inc.)
- Support custom pattern additions

File structure: SKILL.md, subscription_audit.py, pattern_matcher.py, subscription_database.json, requirements.txt

## Response snapshot

Created 6 files in `.claude/skills/subscription-audit/`:

1. **subscription_database.json** — Curated vendor pattern database with 44 SaaS vendors across 13 categories, 9 duplicate groups (video streaming, music streaming, cloud storage, project management, etc.), and typical pricing tiers for price-increase detection.

2. **pattern_matcher.py** — `PatternMatcher` class with vendor name normalization (strips Inc/LLC/Ltd/Corp, domains like .com/.io, collapses whitespace), fuzzy matching via bigram similarity (no external deps, 0.65 threshold), `detect_price_increase()` comparing last 2 charges + typical tier pricing, `detect_duplicates()` using the duplicate_groups from the database, and `add_custom_pattern()` for runtime additions.

3. **subscription_audit.py** — Main UV-runnable script (PEP 723 headers: jinja2, python-dotenv). `SubscriptionAuditor` class loads transactions from 5 vault sources (Logs/payments.json, Logs/accounting.json, Accounting/expenses/*.md, Accounting/payments/*.md, Accounting/invoices/*.md). Groups by vendor using PatternMatcher, detects frequency (weekly/biweekly/monthly/quarterly/annual), checks vault activity in completed/Done/Logs for 30-day recency, flags issues (no_activity, price_increases, duplicates), calculates savings, tracks changes vs previous audit via Logs/subscription_audits.json, renders Jinja2 report, saves to Reports/.

4. **templates/audit_report_template.md** — Jinja2 template with 6 sections: Summary table, Active Subscriptions table, Category Breakdown, Flagged Issues (3 subsections), Cancellation Recommendations with annual savings, Changes Since Last Audit.

5. **requirements.txt** — jinja2, python-dotenv (minimal — no fuzzy matching library needed).

6. **SKILL.md** — Full documentation with architecture, vault data sources, pattern matching details, frequency detection table, CLI options.

Key differentiator from ceo-briefing subscription_analyzer.py: vendor pattern database with fuzzy matching, price increase detection against known tiers, duplicate group detection, historical change tracking between audits, dedicated audit report format.

## Outcome

- ✅ Impact: Complete subscription audit skill with vendor pattern matching, waste detection, and savings recommendations
- 🧪 Tests: `uv run subscription_audit.py --vault-path ../../../obsidian-vault`
- 📁 Files: 6 files created in .claude/skills/subscription-audit/
- 🔁 Next prompts: None specified
- 🧠 Reflection: The bigram similarity approach avoids adding thefuzz/rapidfuzz as dependencies while still providing reasonable fuzzy matching for vendor name variations. The JSON vendor database is extensible without code changes.

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Manual verification PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add unit tests with mock vault data; expand vendor database based on real transaction data
