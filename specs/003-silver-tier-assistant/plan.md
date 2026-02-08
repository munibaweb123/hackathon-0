# Implementation Plan: Silver Tier — Functional Assistant

**Branch**: `003-silver-tier-assistant` | **Date**: 2026-02-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-silver-tier-assistant/spec.md`

## Summary

The Silver Tier extends the Bronze Tier AI Employee with external platform monitoring (Gmail, LinkedIn, WhatsApp via watchers), automated LinkedIn posting with human approval, a Claude-powered reasoning loop that produces Plan.md files, an MCP server for controlled external actions, and a task scheduler. The architecture follows a **Perception → Reasoning → Action** pipeline with mandatory human approval gates between stages.

## Technical Context

**Language/Version**: Python 3.8+ (backend/watchers), TypeScript/Node.js (Next.js 16 dashboard)
**Primary Dependencies**:
- Backend: FastAPI 0.115, watchdog 3.0+, PyYAML 6.0+, google-api-python-client, playwright (for WhatsApp)
- Dashboard: Next.js 16.1.6, React 19, Tailwind CSS 4, Radix UI, googleapis
- Reasoning: Claude API (claude-sonnet-4-20250514 or claude-opus-4-5-20251101)

**Storage**: File-based (Obsidian vault structure) — no database required
**Testing**: pytest (Python), Jest/Vitest (TypeScript)
**Target Platform**: Linux/macOS server (WSL supported), Web browser (dashboard)
**Project Type**: Web application (Python backend + Next.js dashboard)
**Performance Goals**:
- Watcher polling: <60s detection latency
- Reasoning loop: Plan.md generation <60s per event (SC-004)
- MCP execution: >90% success rate (SC-005)

**Constraints**:
- All external actions require human approval (constitution mandate)
- No auto-approve for LinkedIn posts in Silver Tier
- Rate limits: LinkedIn API (100 posts/day), Gmail API (250 quota units/day)

**Scale/Scope**: Single-user system, ~10 dashboard pages, 7 Agent Skills, 3 watchers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Human Authority** | ✅ PASS | All external actions require explicit human approval via file-based workflow (FR-007). No irreversible actions without consent. |
| **Explainability** | ✅ PASS | Claude reasoning loop generates Plan.md with context, analysis, and recommended actions. All operations logged with timestamps (FR-010). |
| **Minimal Autonomy** | ✅ PASS | AI proposes actions; humans approve/reject. System defaults to requesting guidance on ambiguous events. |
| **Security & Privacy** | ✅ PASS | OAuth for Gmail/LinkedIn (no stored credentials). Playwright session for WhatsApp. No API keys in code. |
| **Deterministic Behavior** | ✅ PASS | Watcher polling at fixed intervals. Plan.md follows consistent format. Actions execute only on explicit approval. |
| **File-Based Operations** | ✅ PASS | All state changes via vault folders. Events stored as structured markdown/JSON files. |
| **Transparency & Auditability** | ✅ PASS | Tamper-evident logging with SHA-256 hashes. Complete audit trail in vault. |

**Bronze Tier Constraints** (N/A for Silver — Silver tier explicitly allows controlled external communication):
- ❌ Read/write only → Superseded by MCP server for approved external actions
- ❌ No external communication → Superseded by watchers (inbound) and MCP (outbound)
- ❌ No emails/API calls → Superseded by Gmail/LinkedIn integrations

**Human-in-the-Loop Rules**:
- ✅ Approval-based actions: All sensitive actions create `APPROVAL_REQUIRED_*.md` files
- ✅ No irreversible actions without explicit approval: Moving file to `/Approved` folder triggers execution
- ✅ Auditability through logs: All approvals logged with timestamps and operator identity

## Project Structure

### Documentation (this feature)

```text
specs/003-silver-tier-assistant/
├── plan.md              # This file (/sp.plan command output)
├── research.md          # Phase 0 output (/sp.plan command)
├── data-model.md        # Phase 1 output (/sp.plan command)
├── quickstart.md        # Phase 1 output (/sp.plan command)
├── contracts/           # Phase 1 output (/sp.plan command)
│   ├── mcp-server-api.yaml        # OpenAPI spec for MCP server
│   └── watcher-events.schema.json # JSON Schema for watcher events
└── tasks.md             # Phase 2 output (/sp.tasks command - NOT created by /sp.plan)
```

### Source Code (repository root)

```text
# Bronze Tier Foundation (existing)
src/
├── ai_employee.py           # Main orchestrator
├── file_monitor.py          # Watchdog-based file monitoring
├── vault_manager.py         # Vault directory operations
├── state_manager.py         # File state transitions
├── document_processor.py    # Document processing orchestration
├── approval_system.py       # Approval workflow management
├── security.py              # Constraint enforcement
├── claude_integration.py    # Claude API integration
├── entities.py              # Core dataclasses
└── config.py                # Configuration management

# Agent Skills Framework (existing + Silver extensions)
agent-skills/
├── core/
│   ├── base_skill.py        # Base class for Agent Skills
│   ├── vault_interface.py   # File-based vault operations
│   ├── logger.py            # Tamper-evident logging
│   └── approval_validator.py
├── mcp_server/
│   ├── server.py            # FastAPI MCP server (extend for Silver)
│   └── actions/
│       ├── email_action.py
│       └── linkedin_action.py
├── watchers/
│   ├── watcher_base.py      # Abstract base watcher
│   ├── gmail_watcher.py     # Gmail OAuth watcher
│   ├── linkedin_watcher.py  # LinkedIn OAuth watcher
│   └── whatsapp_watcher.py  # [NEW] Playwright-based WhatsApp watcher
├── skills/
│   ├── reasoning_skill.py   # Claude reasoning loop
│   ├── planning_skill.py    # Plan.md generation
│   ├── communication_skill.py
│   └── execution_skill.py
├── scheduler/
│   └── task_scheduler.py    # Configurable task scheduling
└── cli/
    └── main.py              # Agent skills CLI

# Next.js Dashboard (existing + Silver extensions)
dashboard/
├── src/
│   ├── app/
│   │   ├── page.tsx         # Dashboard home
│   │   ├── approvals/       # Approval management
│   │   ├── gmail/           # Gmail integration
│   │   ├── linkedin/        # LinkedIn integration (extend for posting)
│   │   └── whatsapp/        # [NEW] WhatsApp integration page
│   ├── components/
│   │   ├── ui/              # Shadcn components
│   │   ├── gmail-live.tsx
│   │   ├── linkedin-live.tsx
│   │   └── whatsapp-live.tsx # [NEW] WhatsApp live component
│   └── lib/
│       ├── vault.ts         # Vault operations
│       └── types.ts         # TypeScript interfaces
└── tests/

# Obsidian Vault (data storage)
obsidian-vault/
├── inbox/                   # Incoming events from watchers
├── processing/              # Files being processed
├── pending-approval/        # Awaiting human approval
├── Approved/                # Approved actions (trigger execution)
├── Rejected/                # Rejected actions
├── completed/               # Successfully processed
└── archive/                 # Historical records

tests/
├── contract/                # Contract tests
├── integration/             # Integration tests
└── unit/                    # Unit tests
```

**Structure Decision**: Web application architecture with Python backend (watchers, MCP server, reasoning loop) and Next.js dashboard (human interface). File-based storage using Obsidian vault structure. Builds upon existing Bronze Tier foundation.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Bronze Tier network restriction | Silver Tier requires external API access for watchers and MCP actions | File-only operation cannot fulfill Silver Tier requirements (monitoring external platforms, posting to LinkedIn) |
| OAuth complexity | Required for Gmail/LinkedIn API access | API keys alone insufficient; OAuth provides revocable user-delegated access |
| Playwright for WhatsApp | WhatsApp Business Cloud API requires business verification; Playwright enables personal account automation | Direct API access blocked for personal accounts per spec clarification |

## Implementation Phases

### Phase 0: Research & Unknowns Resolution (see research.md)

Key research areas completed:
1. ✅ WhatsApp Web automation with Playwright — session management, QR code handling
2. ✅ Claude API reasoning loop patterns — structured output, tool use
3. ✅ LinkedIn API posting workflow — OAuth 2.0, content API endpoints
4. ✅ Gmail API polling best practices — incremental sync, push notifications

### Phase 1: Design & Contracts (see data-model.md, contracts/)

Key design artifacts:
1. ✅ Data model for events, plans, approvals, posts
2. ✅ MCP Server API contract (OpenAPI)
3. ✅ Watcher event schema (JSON Schema)
4. ✅ Quickstart guide for developers

### Phase 2: Task Generation (via /sp.tasks)

Task breakdown to be generated after plan approval.
