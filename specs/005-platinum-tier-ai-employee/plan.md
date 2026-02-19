# Implementation Plan: Platinum Tier AI Employee — Cloud+Local Split Architecture

**Branch**: `005-platinum-tier-ai-employee` | **Date**: 2026-02-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-platinum-tier-ai-employee/spec.md`

## Summary

Build a production-grade, always-on AI Employee with a Cloud+Local split architecture. The cloud agent runs 24/7 on a free-tier VM with read-only API access, creating drafts and monitoring services. The local agent runs on the CEO's machine, handling all approvals, sensitive operations, and final execution. Agents communicate exclusively through a Git-synced Obsidian vault with 5-minute polling intervals, single-writer conflict resolution, and claim-by-move coordination. The existing Gold Tier codebase (`.claude/skills/`, `agent-skills/`, `dashboard/`) provides ~70% of needed functionality; the primary new work is the topology split, agent identity system, security boundary enforcement, and deployment automation.

## Technical Context

**Language/Version**: Python 3.10+ (agents, skills, watchers), TypeScript/Node.js (Next.js 16 dashboard)
**Primary Dependencies**: watchdog, google-api-python-client, playwright, anthropic, apscheduler, PyYAML, FastAPI, uvicorn, httpx, gitpython
**Storage**: File-based (Obsidian vault — YAML/JSON/Markdown). No database.
**Testing**: pytest (Python), vitest (TypeScript dashboard)
**Target Platform**: Cloud agent: Ubuntu 22.04 on Oracle Cloud/AWS Free Tier (1 vCPU, 1GB RAM). Local agent: Windows/macOS/Linux (CEO's machine).
**Project Type**: Multi-agent distributed system with shared file-based state
**Performance Goals**: Email draft creation <5 min, vault sync <2 min, dashboard interaction <30s, briefing generation <10 min
**Constraints**: Cloud VM limited to 1 vCPU, 1GB RAM, 50GB storage. Cloud agent: read-only API scopes only. All inter-agent communication async via vault sync (5-min polling). No real-time channel.
**Scale/Scope**: Single-user (CEO), <500 emails/day, <10 social posts/week, <20 payments/month

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Human Authority** | PASS | All sensitive actions (send, post, pay) require explicit CEO approval via local agent. Cloud agent creates drafts only. |
| **Explainability** | PASS | Audit log with hash-chain integrity on both agents. All actions logged with reasoning. |
| **Minimal Autonomy** | PASS | Cloud agent has read-only access, cannot execute any outbound actions. Local agent requires approval for all sensitive operations. |
| **Security & Privacy** | PASS | Trust boundary enforced: cloud agent holds only read-only OAuth tokens. Sensitive credentials (WhatsApp, banking, payment) exclusively on local agent. |
| **Deterministic Behavior** | PASS | File-based workflows with defined state transitions (Drafts → Approved → Done). Polling-based sync at fixed 5-min intervals. |
| **File-Based Operations** | PASS | Obsidian vault is sole communication channel. All state changes are file modifications. |
| **Transparency & Auditability** | PASS | Full audit trail on both agents with tamper-evident hash chains. SyncEvent logging for all vault operations. |
| **HITL Rules** | PASS | No irreversible action without approval. Approval files flow through designated directories. |

**Gate result: PASS** — No violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/005-platinum-tier-ai-employee/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── vault-file-schema.yaml
│   └── agent-config-schema.yaml
└── tasks.md             # Phase 2 output (via /sp.tasks)
```

### Source Code (repository root)

```text
cloud/
├── agent.py                    # Cloud agent entry point
├── config.yaml                 # Cloud-specific orchestrator config
├── Dockerfile                  # Cloud deployment container
├── systemd/
│   └── cloud-agent.service     # systemd unit file
├── skills/                     # Symlinks or copies of cloud-safe skills
│   ├── gmail-watcher/          → .claude/skills/gmail-watcher/
│   ├── health-monitor/         → .claude/skills/health-monitor/
│   ├── ceo-briefing-generator/ → .claude/skills/ceo-briefing-generator/
│   ├── subscription-audit/     → .claude/skills/subscription-audit/
│   └── vault-sync/             → .claude/skills/vault-sync/
└── credentials/
    └── readonly-tokens.enc     # Read-only OAuth tokens only

local/
├── agent.py                    # Local agent entry point
├── config.yaml                 # Local-specific orchestrator config
├── skills/                     # Symlinks or copies of local-safe skills
│   ├── approval-manager/       → .claude/skills/approval-manager/
│   ├── email-sender-mcp/       → .claude/skills/email-sender-mcp/
│   ├── social-poster-mcp/      → .claude/skills/social-poster-mcp/
│   ├── payment-handler-mcp/    → .claude/skills/payment-handler-mcp/
│   ├── whatsapp-watcher/       → .claude/skills/whatsapp-watcher/
│   ├── invoice-generator/      → .claude/skills/invoice-generator/
│   └── vault-sync/             → .claude/skills/vault-sync/
└── credentials/
    └── sensitive-tokens.enc    # Full-access tokens (send, pay, post)

agent-skills/
├── core/
│   ├── agent_identity.py       # NEW: Agent ID, zone, heartbeat, capabilities
│   ├── topology.py             # NEW: Cloud/local routing, skill assignment
│   ├── draft_lifecycle.py      # NEW: Draft creation, expiration (48h), archival
│   └── security_boundary.py    # NEW: Credential scope enforcement
├── ... (existing modules unchanged)

dashboard/                      # Existing Next.js 16 app (extended)
├── src/app/
│   ├── drafts/                 # NEW: Draft review/approval page
│   ├── leads/                  # NEW: Lead pipeline page
│   ├── sync-status/            # NEW: Vault sync health page
│   └── agent-topology/         # NEW: Cloud/local agent status page

obsidian-vault/                 # Extended vault structure
├── Needs_Action/
│   └── cloud/                  # Cloud-created action items
│       └── leads/              # Extracted leads
├── Drafts/
│   ├── email/                  # Email draft replies
│   ├── social/                 # Social media post drafts
│   ├── payments/               # Payment instruction drafts
│   └── briefings/              # CEO briefing drafts
├── Signals/
│   ├── health/                 # Health alerts from cloud
│   ├── auth/                   # Token refresh requests
│   └── sync/                   # Sync conflict alerts
├── Pending_Approval/
│   └── local/                  # Items awaiting CEO approval
├── Approved/                   # CEO-approved items
├── Done/
│   ├── payments/               # Completed payment receipts
│   └── expired/                # Auto-expired drafts (48h)
└── Updates/                    # Cloud writes status updates here
```

**Structure Decision**: Multi-agent split with `cloud/` and `local/` top-level directories, each containing an agent entry point and config. Shared code remains in `agent-skills/` (imported by both). Standalone skills in `.claude/skills/` are symlinked into the appropriate agent's `skills/` directory based on trust zone assignment. The Obsidian vault gains new subdirectories (`Drafts/`, `Signals/`, `Updates/`) for structured inter-agent communication.

## Complexity Tracking

No constitution violations requiring justification. The cloud/local split is the minimal architecture needed to satisfy the trust boundary requirements (FR-001, FR-002).

## Architecture Decisions

### AD-1: Agent Topology — Symlink-Based Skill Assignment

Each agent's `skills/` directory contains symlinks to the canonical skill implementations in `.claude/skills/`. A `topology.yaml` file declares which skills belong to which agent zone. This avoids code duplication while enforcing the trust boundary at the filesystem level.

**Alternatives rejected:**
- Separate copies of skills per agent: duplication burden, drift risk.
- Single orchestrator with remote dispatch: requires real-time network channel, violates async-only constraint.

### AD-2: Vault Directory Protocol — Zone-Scoped Write Paths

Cloud agent writes only to `/Needs_Action/cloud/`, `/Drafts/`, `/Signals/`, `/Updates/`. Local agent writes only to `/Pending_Approval/local/`, `/Approved/`, `/Done/`. Both read everything. This is enforced by the `security_boundary.py` module which wraps `vault_interface.py` with write-path validation.

**Alternatives rejected:**
- OS-level file permissions: fragile across Git sync, platform-dependent.
- Separate vaults per agent: defeats the purpose of shared state.

### AD-3: Draft Lifecycle — 48-Hour Expiration with Archival

Drafts carry an `expires-at` timestamp (created-at + 48h). The cloud agent's expiration sweeper runs hourly, moving expired drafts to `/Done/expired/`. This prevents dashboard clutter while preserving data for audit.

### AD-4: Credential Scope Enforcement

Cloud agent's `credentials/` directory contains only read-only OAuth tokens. The `security_boundary.py` module validates that cloud-zone skills cannot access sensitive credential paths. The local agent holds the full credential set. Token refresh is signaled via vault files in `/Signals/auth/`.

### AD-5: Git Sync as Sole Transport

All inter-agent communication uses Git-based vault sync with 5-minute polling. No WebSocket, webhook, or direct network channel between agents. This keeps the architecture simple, auditable, and resilient to network interruptions.

**Tradeoff accepted:** 5-minute latency for inter-agent communication. Acceptable because the use cases (email drafts, social posts, briefings) are not latency-sensitive.
