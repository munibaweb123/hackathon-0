# Company Handbook

This is your AI Employee's reference document. It describes your business context so the AI can make better decisions.

## About the Company

- **Company Name:** [Your Company Name]
- **Industry:** [Your Industry]
- **Your Role:** [CEO / Founder / Manager]

## Communication Rules

### Email Priority
- **High Priority:** Emails from clients, invoices, urgent requests
- **Medium Priority:** Team updates, meeting requests, follow-ups
- **Low Priority:** Newsletters, promotions, automated notifications

### Response Guidelines
- Client emails: Draft a professional reply within 1 hour
- Invoice emails: Flag for review, extract amount and due date
- Meeting requests: Check calendar availability, suggest times
- Newsletters: Archive, no action needed

## Key Contacts

| Name | Email | Relationship | Notes |
|------|-------|-------------|-------|
| [Contact 1] | [email] | Client | VIP - always respond quickly |
| [Contact 2] | [email] | Supplier | Monthly invoices |
| [Contact 3] | [email] | Team | Internal updates |

## Business Hours

- **Work Days:** Monday - Friday
- **Hours:** 9:00 AM - 6:00 PM
- **Timezone:** [Your Timezone]
- **After Hours:** Only respond to urgent/high priority

## Gmail Setup Instructions

### Step 1: Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or select existing)
3. Enable the **Gmail API**
4. Go to **Credentials** → Create **OAuth 2.0 Client ID**
5. Download the JSON file as `credentials.json`
6. Place it in the project root (next to the bronze/ folder)

### Step 2: First-Time Authentication

```bash
# Run the watcher once — it will open a browser for OAuth
uv run bronze/gmail_watcher.py --vault-path ./obsidian-vault --once

# After approving, a token.json file is created automatically
# Future runs won't need the browser
```

### Step 3: Environment Variables

Create a `.env` file in the project root:

```env
# Gmail
GMAIL_CREDENTIALS_PATH=./credentials.json
GMAIL_TOKEN_PATH=./token.json

# Optional: Anthropic API key for Claude processor
ANTHROPIC_API_KEY=sk-ant-...
```

## Folder Structure

```
obsidian-vault/
├── Dashboard.md          ← You are here! Overview of everything
├── Company_Handbook.md   ← This file. Business context for the AI
├── Needs_Action/         ← New tasks the AI detected
├── Plans/                ← AI-generated response plans
├── Done/                 ← Completed tasks (archive)
└── Logs/                 ← Activity logs for debugging
```
