---
id: "0013"
title: Social Poster MCP Skill
stage: green
date: 2026-02-15
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: implement
labels: ["mcp", "social-media", "facebook", "instagram", "twitter", "hitl", "approval"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/social-poster-mcp/approval_handler.js
  - .claude/skills/social-poster-mcp/facebook_client.js
  - .claude/skills/social-poster-mcp/instagram_client.js
  - .claude/skills/social-poster-mcp/twitter_client.js
  - .claude/skills/social-poster-mcp/mcp_server.js
  - .claude/skills/social-poster-mcp/package.json
  - .claude/skills/social-poster-mcp/.env.example
  - .claude/skills/social-poster-mcp/SKILL.md
tests:
  - manual: npm run inspect with MCP Inspector to test tool listing
  - manual: draft_twitter_post with >280 chars to verify character limit validation
  - manual: check approval file creation in pending-approval/
---

## Prompt

Create an Agent Skill called 'social-poster-mcp' that provides an MCP server for posting to Facebook, Instagram, and Twitter/X. Requirements: MCP server protocol with 4 tools (draft_facebook_post, draft_instagram_post, draft_twitter_post, get_post_analytics), official APIs, HITL approval pattern (pending-approval/ → Approved/), image attachments, character limits per platform, post URLs and engagement metrics, logging to Logs/social_media.json. File structure: SKILL.md, mcp_server.js, facebook_client.js, instagram_client.js, twitter_client.js, approval_handler.js, package.json.

## Response snapshot

Created 8 files in `.claude/skills/social-poster-mcp/`:

1. **approval_handler.js** — HITL file-based approval handler. Creates `APPROVAL_REQUIRED_<platform>_<id>.md` files in `pending-approval/` with YAML frontmatter and decision instructions. Scans `Approved/` and `Rejected/` folders for status checks.

2. **facebook_client.js** — Meta Graph API v19.0 client. Supports text posts (`/feed`), link posts, and image posts (`/photos` with multipart upload). Gets engagement metrics (likes, comments, shares). 63,206 char limit. Retry with exponential backoff.

3. **instagram_client.js** — Meta Graph API v19.0 with two-step Container Publishing flow (`/media` → `/media_publish`). Requires public image URL (MEDIA_HOST_URL env var for vault files). 2,200 char caption limit. Gets likes/comments metrics.

4. **twitter_client.js** — Twitter API v2 with OAuth 1.0a HMAC-SHA1 signature. Media upload via v1.1 `/media/upload.json`. 280 char limit. Gets public metrics (likes, retweets, replies, impressions). Bearer token for read-only analytics.

5. **mcp_server.js** — MCP server with stdio transport, 4 tools. All draft_* tools route through ApprovalHandler (no direct posting). Platform clients lazily initialized for analytics. Same pattern as email-sender-mcp.

6. **package.json** — Minimal deps: `@modelcontextprotocol/sdk` + `dotenv`. All API calls use native `fetch()` (Node 18+).

7. **.env.example** — Template for Facebook, Instagram, Twitter credentials + VAULT_PATH.

8. **SKILL.md** — Full documentation with tool schemas, approval workflow, architecture diagram, character limits, Claude Desktop config.

## Outcome

- ✅ Impact: Complete social media MCP server with HITL approval for all 3 platforms
- 🧪 Tests: Manual verification via MCP Inspector; character limit validation built-in
- 📁 Files: 8 files created in .claude/skills/social-poster-mcp/
- 🔁 Next prompts: npm install, configure API credentials, test with MCP Inspector
- 🧠 Reflection: Native fetch() kept dependencies minimal (only 2 npm packages). HITL approval pattern ensures no accidental public posts.

## Evaluation notes (flywheel)

- Failure modes observed: None — clean implementation following established email-sender-mcp pattern
- Graders run and results (PASS/FAIL): N/A — manual testing required with API credentials
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add scheduled posting support (cron-based delayed publish after approval)
