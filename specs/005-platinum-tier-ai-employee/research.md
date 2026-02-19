# Research: Platinum Tier AI Employee

**Feature**: 005-platinum-tier-ai-employee
**Date**: 2026-02-18

## Research Topics

### R-1: Cloud VM Deployment Strategy (Oracle Cloud Free Tier)

**Decision**: Docker container on Oracle Cloud Always-Free ARM instance (Ampere A1, 1 OCPU, 6GB RAM, 47GB storage).

**Rationale**: Oracle Cloud's Always-Free tier provides significantly more resources than AWS Free Tier (t2.micro: 1 vCPU, 1GB RAM, 30GB storage). The ARM instance is permanently free (not 12-month limited). Docker provides consistent deployment across environments and easy restart/update via systemd.

**Alternatives considered**:
- AWS Free Tier (t2.micro): Less RAM (1GB vs 6GB), 12-month expiry. Viable fallback.
- Bare metal systemd: Simpler but less portable, harder to reproduce environment.
- Kubernetes: Overkill for single-agent deployment on free tier.

### R-2: Git Sync Implementation for Multi-Agent Coordination

**Decision**: Reuse existing `vault-sync` skill with enhanced conflict resolution rules for the new vault directory structure.

**Rationale**: The Gold Tier `vault-sync` skill already implements Git-based sync with claim-by-move, conflict resolution, and offline queue. The existing conflict rules need extension for the new directories (`/Drafts/`, `/Signals/`, `/Updates/`), but the core sync loop is production-ready.

**Enhancements needed**:
- Add conflict rules: `Drafts/**` → `cloud_wins`, `Signals/**` → `cloud_wins`, `Approved/**` → `local_wins`, `Done/**` → `local_wins`
- Add `sync-interval: 300` (5 minutes) to config
- Add heartbeat file: each agent writes `Signals/heartbeat/{agent-id}.yaml` every sync cycle

**Alternatives considered**:
- rsync: No conflict resolution, no audit trail, no merge capability.
- Syncthing: Real-time sync but harder to control, no built-in conflict rules.
- Custom WebSocket: Adds complexity, requires open ports, violates async-only principle.

### R-3: Read-Only OAuth Scope Configuration

**Decision**: Gmail API — `gmail.readonly` scope. Social platforms — read-only scopes where available.

**Rationale**: Minimizes blast radius if cloud VM is compromised. Read-only scopes are sufficient for monitoring and draft creation (drafts are vault files, not Gmail drafts).

**Scope mapping**:
- Gmail: `https://www.googleapis.com/auth/gmail.readonly` (read messages, no send)
- LinkedIn: `r_liteprofile`, `r_organization_social` (read only)
- Twitter/X: OAuth 2.0 with `tweet.read`, `users.read` (read only)
- Facebook: `pages_read_engagement` (read only)

**Alternatives considered**:
- Gmail `gmail.compose` scope for cloud: Would allow cloud to create actual Gmail drafts, but violates trust boundary.
- No API access for cloud: Would require local agent to push email data to vault, adding latency.

### R-4: Agent Identity and Registration Protocol

**Decision**: File-based agent registration via `Signals/agents/{agent-id}.yaml` with heartbeat timestamps.

**Rationale**: Consistent with the file-based architecture. Each agent writes its identity file on startup and updates it every sync cycle. The other agent discovers peers by reading the `Signals/agents/` directory.

**Identity file format**:
```yaml
agent-id: cloud-001
zone: cloud
status: running
started-at: 2026-02-18T08:00:00Z
last-heartbeat: 2026-02-18T14:30:00Z
capabilities:
  - gmail-watcher
  - health-monitor
  - ceo-briefing-generator
  - subscription-audit
  - vault-sync
sync-interval: 300
```

**Alternatives considered**:
- Centralized registry service: Adds network dependency, violates async-only principle.
- Database-backed registration: No database in the architecture.

### R-5: Draft File Format and Lifecycle

**Decision**: YAML-frontmatter Markdown files with standardized metadata, matching existing vault file patterns.

**Rationale**: Consistent with the existing Obsidian vault conventions. YAML frontmatter provides structured metadata for programmatic processing while Markdown body is human-readable in Obsidian.

**Draft file format**:
```yaml
---
draft-id: draft-email-2026-02-18-001
type: email-reply
priority: high
created-at: 2026-02-18T08:15:00Z
expires-at: 2026-02-20T08:15:00Z
status: pending
source:
  email-id: msg-abc123
  from: client@example.com
  subject: "Q1 Report Review"
context:
  handbook-reference: "Client Communication Guidelines"
  contact-history: 5 previous interactions
---

## Suggested Reply

Dear [Client],

Thank you for sharing the Q1 report...

## Original Email Summary

[Summary of the email being replied to]
```

### R-6: Security Boundary Enforcement Approach

**Decision**: Application-level path validation via a `SecurityBoundary` wrapper class around `VaultInterface`.

**Rationale**: OS-level file permissions don't survive Git sync operations and are platform-dependent (Windows vs Linux). Application-level enforcement is portable, testable, and provides clear error messages.

**Implementation approach**:
- `SecurityBoundary(zone='cloud', vault_path='/path/to/vault')` wraps `VaultInterface`
- Write operations are validated against an allowlist of directory prefixes per zone
- Read operations are unrestricted (both agents can read everything)
- Violation attempts are logged to the audit log and raise `SecurityBoundaryViolation`

**Alternatives considered**:
- OS file permissions (chown/chmod): Not portable, broken by Git operations.
- Git hooks (server-side): Requires custom Git server setup, complex.
- Separate Git repos per zone: Defeats shared state, complex merge.

### R-7: Dashboard Extension Strategy

**Decision**: Add 4 new Next.js pages to the existing dashboard, reusing existing layout and component patterns.

**Rationale**: The Gold Tier dashboard already has 15+ pages with consistent patterns (shadcn/ui, Tailwind, vault file reading). New pages follow the same patterns.

**New pages**:
- `/drafts` — Review, edit, approve/reject drafts from all categories
- `/leads` — Lead pipeline view with categorization and urgency
- `/sync-status` — Vault sync health, last sync times, conflict history
- `/agent-topology` — Cloud/local agent status, heartbeats, capabilities
