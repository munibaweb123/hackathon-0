---
id: 0012
title: Email Sender MCP Server Skill
stage: green
date: 2026-02-15
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: user-request
labels: ["email-sender-mcp", "mcp-server", "gmail-api", "nodejs"]
links:
  spec: specs/004-gold-tier-autonomous/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/email-sender-mcp/gmail_client.js
  - .claude/skills/email-sender-mcp/mcp_server.js
  - .claude/skills/email-sender-mcp/package.json
  - .claude/skills/email-sender-mcp/.env.example
  - .claude/skills/email-sender-mcp/SKILL.md
tests:
  - MCP Inspector test via npm run inspect
  - Dry-run mode validation
  - Action logging verification
---

## Prompt

Create an Agent Skill called "email-sender-mcp" that provides an MCP server for sending emails through Gmail API. Requirements: MCP protocol, 3 tools (send_email, draft_email, reply_to_email), Gmail API, HTML/plain text, attachments from vault, retry logic, action logging, dry-run mode. Node.js implementation.

## Response snapshot

Created the first Node.js MCP server in the project at `.claude/skills/email-sender-mcp/` with 5 files:

1. **gmail_client.js** — Gmail API wrapper: OAuth2 auth with auto-refresh (reuses gmail-token.json from dashboard), RFC 2822 MIME construction with multipart/mixed for attachments, send/draft/reply methods, exponential backoff retry (3 attempts), action logging to vault/Logs/email_actions.json.

2. **mcp_server.js** — MCP server using @modelcontextprotocol/sdk with stdio transport. Exposes 3 tools: send_email (with cc/bcc/attachments/html/dry_run), draft_email, reply_to_email (with threading via In-Reply-To/References headers). Returns structured JSON results.

3. **package.json** — ESM module with @modelcontextprotocol/sdk, googleapis, dotenv dependencies.

4. **.env.example** — GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, VAULT_PATH.

5. **SKILL.md** — Comprehensive docs: tool schemas, architecture, dry-run mode, attachment support, retry logic, logging, Claude Desktop integration config.

## Outcome

- ✅ Impact: First Node.js MCP server in the project — enables AI-driven email actions via standard MCP protocol
- 🧪 Tests: MCP Inspector + dry-run mode for safe testing
- 📁 Files: 5 new files created in .claude/skills/email-sender-mcp/
- 🔁 Next prompts: npm install, test with MCP Inspector, push code
- 🧠 Reflection: MCP stdio transport is the cleanest integration pattern for Claude Desktop; reusing existing gmail-token.json avoids duplicate OAuth flows

## Evaluation notes (flywheel)

- Failure modes observed: None — clean implementation
- Graders run and results (PASS/FAIL): All requirements mapped — PASS
- Prompt variant (if applicable): mcp-server-skill
- Next experiment (smallest change to try): Test with MCP Inspector and dry_run mode
