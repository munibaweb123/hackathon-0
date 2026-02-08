---
name: linkedin-content
description: LinkedIn content generation and posting skill for the AI Employee. Handles post creation, approval workflow, and publishing through the LinkedIn API.
---

# LinkedIn Content Skill

Generates business-relevant LinkedIn posts and manages the full lifecycle: draft → approval → publish.

## Architecture

```
Event/Schedule → LinkedIn Content Skill → Post Draft → Approval → MCP Action → LinkedIn API
```

- All posts MUST go through human approval before publishing
- Content generated via Claude API or manual input
- Posts tracked as files in `obsidian-vault/posts/`

## Key Files

| File | Purpose |
|------|---------|
| `agent-skills/watchers/linkedin_watcher.py` | LinkedIn notification monitoring |
| `agent-skills/core/post_manager.py` | Post lifecycle management |
| `agent-skills/core/approval_generator.py` | Creates APPROVAL_REQUIRED files |
| `agent-skills/mcp_server/actions/linkedin_action.py` | LinkedIn API posting |
| `dashboard/src/app/linkedin/page.tsx` | LinkedIn dashboard page |
| `dashboard/src/app/api/linkedin/` | OAuth routes + posting API |

## Post Lifecycle

```
draft → pending_approval → approved → published
                        → rejected (archived)
                        → expired (after 24h, archived)
                        → failed (on API error)
```

## Post File Format

```yaml
---
id: <uuid>
type: linkedin_post
status: draft
created_at: 2026-02-08T14:30:00Z
content_length: 450
generation_context:
  source: ai_generated
  topic: business insights
  model: claude-sonnet-4-20250514
---
# LinkedIn Post Draft

[Post content here]
```

## Content Generation

When generating content via Claude:
- Keep under 1300 characters (LinkedIn optimal)
- Use a hook in the first line
- Include 2-3 relevant hashtags
- Focus on providing value, not selling
- Sound authentic, not robotic

## Approval Flow

1. Post created as draft in `obsidian-vault/posts/`
2. `APPROVAL_REQUIRED_linkedin_post_<id>.md` created in `pending-approval/`
3. Human moves file to `Approved/` or `Rejected/`
4. Approval watcher detects decision
5. If approved: MCP server publishes via LinkedIn API
6. Post status updated to `published` with LinkedIn post ID

## LinkedIn API Integration

Uses OAuth tokens from dashboard (`linkedin-token.json`):
- Token shared between Next.js dashboard and Python backend
- 401 response → switch to mock mode
- Rate limit (429) → exponential backoff

## Business Alignment

Posts are validated against business rules:
- No spam/scam content
- Professional tone
- Relevant to business profile
- Within character limits
