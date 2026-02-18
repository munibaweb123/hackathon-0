---
name: email-sender-mcp
description: MCP server for sending emails through Gmail API. Exposes send_email, draft_email, and reply_to_email tools via the Model Context Protocol.
---

# Email Sender MCP Server

An MCP (Model Context Protocol) server that exposes Gmail email tools — send, draft, and reply — to any MCP-compatible client (Claude Desktop, MCP Inspector, custom agents).

## Quick Start

```bash
cd .claude/skills/email-sender-mcp
npm install

# Test with MCP Inspector
npm run inspect

# Or run directly
node mcp_server.js
```

## Prerequisites

1. **Node.js 18+**
2. **Gmail API enabled** in Google Cloud Console
3. **OAuth2 credentials** — complete the dashboard OAuth flow first, or place `client-secret.json` in the project root
4. **Token file** — `gmail-token.json` (created by the dashboard OAuth flow or gmail-watcher)

## MCP Tools

### 1. `send_email`

Send an email through Gmail.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `to` | string | yes | Recipient(s), comma-separated |
| `subject` | string | yes | Subject line |
| `body` | string | yes | Email body |
| `cc` | string | no | CC recipients |
| `bcc` | string | no | BCC recipients |
| `attachments` | string[] | no | Filenames from vault `Attachments/` |
| `html` | boolean | no | Send as HTML (default: plain text) |
| `dry_run` | boolean | no | Validate only, don't send |

**Returns:** `{ success, messageId, threadId }`

### 2. `draft_email`

Create a draft in Gmail without sending.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `to` | string | yes | Recipient(s) |
| `subject` | string | yes | Subject line |
| `body` | string | yes | Email body |
| `html` | boolean | no | Draft as HTML |

**Returns:** `{ success, draftId, messageId }`

### 3. `reply_to_email`

Reply to an existing email, maintaining thread.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message_id` | string | yes | Gmail message ID to reply to |
| `body` | string | yes | Reply body |
| `reply_all` | boolean | no | Reply to all recipients |
| `html` | boolean | no | Reply as HTML |

**Returns:** `{ success, messageId, threadId }`

## Architecture

```
MCP Client (Claude Desktop / Inspector)
       │  stdio
       ▼
  mcp_server.js (MCP protocol handler)
       │
       ▼
  gmail_client.js (Gmail API wrapper)
       │
       ├──▶ Gmail API (send/draft/reply)
       ├──▶ vault/Attachments/ (read attachments)
       └──▶ vault/Logs/email_actions.json (audit log)
```

## Dry-Run Mode

Pass `dry_run: true` to `send_email` to validate parameters without actually sending:

```json
{
  "success": true,
  "action": "send_email",
  "mode": "dry_run",
  "details": {
    "to": "user@example.com",
    "subject": "Test",
    "bodyLength": 42,
    "attachments": [],
    "html": false
  },
  "message": "Dry run — email was NOT sent. Parameters validated successfully."
}
```

## Attachments

Attachments are loaded from the vault's `Attachments/` folder. Supported types:

| Extension | MIME Type |
|-----------|----------|
| `.pdf` | application/pdf |
| `.docx` | application/vnd.openxmlformats-officedocument.wordprocessingml.document |
| `.xlsx` | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| `.png` | image/png |
| `.jpg/.jpeg` | image/jpeg |
| `.gif` | image/gif |
| `.txt` | text/plain |
| `.csv` | text/csv |
| `.zip` | application/zip |

## Retry Logic

Transient failures (HTTP 429, 500, 503, network errors) are automatically retried:
- 3 retries with exponential backoff
- Base delay: 1 second, doubling each attempt
- Random jitter added to prevent thundering herd

## Action Logging

Every email action (send, draft, reply) is logged to `vault/Logs/email_actions.json`:

```json
[
  {
    "timestamp": "2026-02-15T10:30:00.000Z",
    "action": "send_email",
    "to": "user@example.com",
    "subject": "Meeting Notes",
    "messageId": "18f3a2b...",
    "threadId": "18f3a2b..."
  }
]
```

## Claude Desktop Integration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "email-sender": {
      "command": "node",
      "args": ["/path/to/.claude/skills/email-sender-mcp/mcp_server.js"],
      "env": {
        "GMAIL_CLIENT_ID": "your-client-id",
        "GMAIL_CLIENT_SECRET": "your-secret",
        "VAULT_PATH": "/path/to/obsidian-vault"
      }
    }
  }
}
```

## File Structure

```
.claude/skills/email-sender-mcp/
├── SKILL.md          # This documentation
├── mcp_server.js     # MCP server (stdio transport)
├── gmail_client.js   # Gmail API wrapper
├── package.json      # Dependencies
└── .env.example      # Credential template
```

## Error Handling

| Error | Behavior |
|-------|----------|
| No token file | Clear error message with setup instructions |
| Token expired | Auto-refresh via OAuth2 refresh_token |
| Rate limited (429) | Retry with exponential backoff |
| Server error (5xx) | Retry with exponential backoff |
| Attachment not found | Error with file path in message |
| Invalid recipient | Gmail API returns validation error |
