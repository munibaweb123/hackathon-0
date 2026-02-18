---
name: social-poster-mcp
description: MCP server for posting to Facebook, Instagram, and Twitter/X with HITL approval. Drafts go through pending-approval/ before publishing.
---

# Social Poster MCP Server

An MCP (Model Context Protocol) server that exposes social media posting tools — Facebook, Instagram, and Twitter/X — with Human-in-the-Loop (HITL) approval. All posts are drafted first; a human must approve before anything gets published.

## Quick Start

```bash
cd .claude/skills/social-poster-mcp
npm install

# Test with MCP Inspector
npm run inspect

# Or run directly
node mcp_server.js
```

## Prerequisites

1. **Node.js 18+** (uses native `fetch()`)
2. **Facebook**: Meta Developer App with `pages_manage_posts` permission + Page Access Token
3. **Instagram**: Meta Developer App with `instagram_content_publish` permission + IG Business Account ID
4. **Twitter/X**: Developer App with OAuth 1.0a credentials (API key, secret, access token, access token secret)

## MCP Tools

### 1. `draft_facebook_post`

Draft a Facebook Page post for approval.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | yes | Post text (max 63,206 chars) |
| `link` | string | no | URL to share |
| `image_file` | string | no | Image from vault `Attachments/` |

**Returns:** `{ approvalId, approvalFile, status: "pending_approval" }`

### 2. `draft_instagram_post`

Draft an Instagram post for approval. Requires an image.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `caption` | string | yes | Post caption (max 2,200 chars) |
| `image_url` | string | no* | Public URL of the image |
| `image_file` | string | no* | Image from vault (requires `MEDIA_HOST_URL`) |

*One of `image_url` or `image_file` is required.

**Returns:** `{ approvalId, approvalFile, status: "pending_approval" }`

### 3. `draft_twitter_post`

Draft a tweet for approval.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | yes | Tweet text (max 280 chars) |
| `image_file` | string | no | Image from vault `Attachments/` |

**Returns:** `{ approvalId, approvalFile, status: "pending_approval" }`

### 4. `get_post_analytics`

Get engagement metrics for a published post. No approval needed.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `platform` | string | yes | `facebook`, `instagram`, or `twitter` |
| `post_id` | string | yes | Platform-specific post/tweet ID |

**Returns (Facebook):** `{ metrics: { likes, comments, shares } }`
**Returns (Instagram):** `{ metrics: { likes, comments, timestamp, permalink } }`
**Returns (Twitter):** `{ metrics: { likes, retweets, replies, impressions } }`

## HITL Approval Workflow

All draft tools follow this flow:

```
1. Claude calls draft_*_post tool
2. Approval file created in vault pending-approval/
   → APPROVAL_REQUIRED_<platform>_<8char_id>.md
3. Human reviews the proposed content in the file
4. Human moves file to Approved/ (or Rejected/)
5. Approval watcher detects and triggers publishing
```

### Approval File Format

```yaml
---
id: a1b2c3d4
type: approval_request
action_type: social_post
platform: twitter
action: tweet
created: 2026-02-15T10:00:00.000Z
expires: 2026-02-16T10:00:00.000Z
risk_level: medium
status: pending
---

# Approval Required: Twitter/X Post

**Platform:** Twitter/X
**Character count:** 142 / 280 ✅

## Proposed Content

```
Just shipped a new feature! Check it out at https://example.com #launch
```

## Decision

To **approve** this post:
→ Move this file to the `Approved/` folder

To **reject** this post:
→ Move this file to the `Rejected/` folder
```

## Architecture

```
MCP Client (Claude Desktop / Inspector)
       │  stdio
       ▼
  mcp_server.js (MCP protocol handler)
       │
       ├──▶ approval_handler.js (creates approval files)
       │         │
       │         └──▶ vault/pending-approval/ → Approved/ → Rejected/
       │
       ├──▶ facebook_client.js (Meta Graph API v19.0)
       ├──▶ instagram_client.js (Meta Graph API v19.0, container publish)
       ├──▶ twitter_client.js (Twitter API v2 + OAuth 1.0a)
       │
       └──▶ vault/Logs/social_media.json (audit log)
```

## Character Limits

| Platform | Limit | Enforcement |
|----------|-------|-------------|
| Facebook | 63,206 chars | Validated before approval file |
| Instagram | 2,200 chars (caption) | Validated before approval file |
| Twitter/X | 280 chars | Validated before approval file |

## Action Logging

Every post action is logged to `vault/Logs/social_media.json`:

```json
[
  {
    "timestamp": "2026-02-15T10:30:00.000Z",
    "platform": "twitter",
    "action": "create_tweet",
    "tweetId": "1234567890",
    "tweetUrl": "https://twitter.com/i/web/status/1234567890",
    "text": "Hello world!"
  }
]
```

## Claude Desktop Integration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "social-poster": {
      "command": "node",
      "args": ["/path/to/.claude/skills/social-poster-mcp/mcp_server.js"],
      "env": {
        "VAULT_PATH": "/path/to/obsidian-vault",
        "FACEBOOK_PAGE_ID": "your-page-id",
        "FACEBOOK_ACCESS_TOKEN": "your-token",
        "INSTAGRAM_USER_ID": "your-ig-id",
        "INSTAGRAM_ACCESS_TOKEN": "your-token",
        "TWITTER_API_KEY": "your-key",
        "TWITTER_API_SECRET": "your-secret",
        "TWITTER_ACCESS_TOKEN": "your-token",
        "TWITTER_ACCESS_TOKEN_SECRET": "your-secret",
        "TWITTER_BEARER_TOKEN": "your-bearer"
      }
    }
  }
}
```

## File Structure

```
.claude/skills/social-poster-mcp/
├── SKILL.md              # This documentation
├── mcp_server.js          # MCP server (stdio transport, 4 tools)
├── approval_handler.js    # HITL file-based approval
├── facebook_client.js     # Meta Graph API for Facebook Pages
├── instagram_client.js    # Meta Graph API for Instagram Business
├── twitter_client.js      # Twitter API v2 + OAuth 1.0a
├── package.json           # Dependencies (minimal — uses native fetch)
└── .env.example           # Credential template
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing API credentials | Clear error on `get_post_analytics`; drafts still work (no API needed) |
| Character limit exceeded | Rejected before creating approval file |
| Image not found | Error with file path in message |
| API rate limited (429) | Retry with exponential backoff (3 retries) |
| Server error (5xx) | Retry with exponential backoff |
| Instagram: no image | Error — IG requires images for all posts |
| Instagram: no public URL | Error with instructions to set `MEDIA_HOST_URL` |
