# Feature Specification: Platinum Tier AI Employee — Cloud+Local Split Architecture

**Feature Branch**: `005-platinum-tier-ai-employee`
**Created**: 2026-02-18
**Status**: Draft
**Input**: User description: "Personal AI Employee - Platinum Tier with Cloud+Local split architecture. Production-grade, always-on system with cloud agent handling drafts/monitoring and local agent handling approvals/sensitive operations."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cloud Agent Monitors Email and Creates Draft Replies (Priority: P1)

The CEO starts their Monday morning. Overnight, the cloud agent has been monitoring the company Gmail inbox 24/7. It detected 12 new emails — 3 flagged as high-priority (from key clients), 5 as routine, and 4 as low-priority/marketing. For each high-priority email, the cloud agent created a draft reply in `/Drafts/email/` with context from the Company Handbook. The CEO opens their local agent, sees the drafts summarized in the dashboard, reviews each one, edits where needed, and approves them for sending.

**Why this priority**: Email is the highest-volume daily communication channel. Automating draft creation while keeping human approval for sending directly addresses the core value proposition — AI handles grunt work, human retains control.

**Independent Test**: Can be fully tested by sending test emails to the monitored inbox and verifying draft files appear in the vault with correct metadata, priority classification, and suggested reply content.

**Acceptance Scenarios**:

1. **Given** the cloud agent is running and monitoring Gmail, **When** a new email arrives from a known client, **Then** a draft reply file is created in `/Drafts/email/` within 5 minutes with sender context, suggested reply, and priority tag.
2. **Given** a draft reply exists in `/Drafts/email/`, **When** the local agent syncs the vault, **Then** the draft appears in the local dashboard for review.
3. **Given** the CEO approves a draft reply via the local agent, **When** the approval is processed, **Then** the email is sent via the local agent's authenticated Gmail session and moved to `/Done/`.
4. **Given** the cloud agent cannot reach Gmail API, **When** the connection fails, **Then** the agent logs the failure to `/Signals/health/` and retries with exponential backoff.

---

### User Story 2 - Vault Sync Between Cloud and Local Agents (Priority: P1)

The cloud agent runs on a remote VM and writes files to its copy of the Obsidian vault. The local agent runs on the CEO's laptop. Both agents synchronize their vault state via Git. When the cloud agent creates new drafts or signals, those files appear on the local vault within the sync interval. When the local agent approves or completes items, those status changes propagate back to the cloud.

**Why this priority**: Without reliable vault sync, the entire split-architecture model breaks down. This is the foundational communication channel between the two agents.

**Independent Test**: Can be tested by writing a file on the cloud vault, triggering a sync, and verifying it appears on the local vault (and vice versa) within the configured interval.

**Acceptance Scenarios**:

1. **Given** the cloud agent writes a new file to `/Needs_Action/cloud/`, **When** the next sync cycle runs, **Then** the file appears in the local agent's vault within 5 minutes.
2. **Given** the local agent moves a file from `/Needs_Action/` to `/Done/`, **When** the next sync cycle runs, **Then** the cloud agent sees the updated file location.
3. **Given** both agents modify different files simultaneously, **When** sync runs, **Then** both changes are merged without conflict.
4. **Given** both agents modify the same file, **When** sync runs, **Then** the conflict is resolved by the rules-based resolver (local agent wins for approval files, cloud agent wins for draft files).
5. **Given** the local agent is offline for 8 hours, **When** it comes back online, **Then** all queued cloud changes are synced without data loss.

---

### User Story 3 - Social Media Post Drafting and Approval Workflow (Priority: P2)

The cloud agent drafts social media posts based on business goals, recent company updates, and a content calendar. It creates post drafts in `/Drafts/social/` with platform-specific formatting (LinkedIn, Twitter/X, Facebook). When the local agent is available, the CEO reviews drafts, edits them, and approves for posting. The local agent then publishes approved posts through authenticated social platform APIs.

**Why this priority**: Social media presence is important for business growth but time-consuming. The draft-approve-publish workflow directly matches the trust boundary model.

**Independent Test**: Can be tested by triggering a content generation cycle and verifying drafts appear with correct platform formatting, then approving a draft and verifying publication to a test/sandbox account.

**Acceptance Scenarios**:

1. **Given** a content calendar entry is due today, **When** the cloud agent processes the calendar, **Then** a platform-formatted draft post appears in `/Drafts/social/` with suggested text, hashtags, and optimal posting time.
2. **Given** a social media draft exists, **When** the CEO approves it via the local agent, **Then** the post is published to the target platform within 2 minutes.
3. **Given** the CEO rejects a draft with feedback, **When** the rejection is synced, **Then** the cloud agent generates a revised draft incorporating the feedback.

---

### User Story 4 - CEO Monday Morning Briefing (Priority: P2)

Every Monday at 7:00 AM, the cloud agent compiles a comprehensive briefing document covering: revenue summary (from accounting data), task velocity (from project tracking), subscription waste analysis, upcoming deadlines, and key business metrics. The briefing is placed in `/Drafts/briefings/` ready for the CEO to review when they start their day.

**Why this priority**: Gives the CEO immediate situational awareness without manual data gathering. High value-to-effort ratio since it aggregates data the system already monitors.

**Independent Test**: Can be tested by triggering a briefing generation cycle and verifying the output document contains all required sections with real or simulated data.

**Acceptance Scenarios**:

1. **Given** it is Monday at 7:00 AM, **When** the briefing scheduler triggers, **Then** a comprehensive briefing document is created in `/Drafts/briefings/` within 10 minutes.
2. **Given** accounting data shows revenue changes, **When** the briefing is generated, **Then** the revenue section includes week-over-week and month-over-month comparisons.
3. **Given** there are overdue tasks, **When** the briefing is generated, **Then** overdue items are highlighted with owner and original deadline.

---

### User Story 5 - Lead Capture and Categorization (Priority: P2)

When the cloud agent detects potential leads in incoming emails (new inquiry, RFP, partnership request), it categorizes them by type and urgency, extracts key details (company name, contact, request summary), and creates a structured lead file in `/Needs_Action/cloud/leads/`. The local agent surfaces these leads in the dashboard for the CEO to review and act on.

**Why this priority**: Lead management directly impacts revenue. Automated capture ensures no opportunity falls through the cracks.

**Independent Test**: Can be tested by sending emails with lead-like content and verifying categorized lead files appear with correct extracted details.

**Acceptance Scenarios**:

1. **Given** an email arrives with a new business inquiry, **When** the cloud agent processes it, **Then** a lead file is created with extracted company name, contact info, request type, and urgency classification.
2. **Given** a lead file exists, **When** the local agent syncs, **Then** the lead appears in the dashboard's lead pipeline view.

---

### User Story 6 - Payment and Banking Operations (Priority: P3)

When invoices are due or payment requests arise, the cloud agent prepares payment instructions in `/Drafts/payments/` with amount, recipient, and context. The local agent — which exclusively holds banking credentials and payment tokens — presents these to the CEO for approval. Upon approval, the local agent executes the payment through the appropriate channel (bank transfer, Stripe, PayPal) and records the transaction in `/Done/payments/`.

**Why this priority**: Financial operations require the highest trust level. Critical for business operations but lower frequency than email/social.

**Independent Test**: Can be tested by creating a payment draft, approving it, and verifying execution against a sandbox/test payment endpoint.

**Acceptance Scenarios**:

1. **Given** an invoice is due within 3 days, **When** the cloud agent detects it, **Then** a payment draft is created in `/Drafts/payments/` with all required details.
2. **Given** a payment is approved by the CEO, **When** the local agent processes it, **Then** the payment is executed and a receipt is recorded in `/Done/payments/`.
3. **Given** a payment amount exceeds a configurable threshold, **When** the CEO approves it, **Then** a secondary confirmation is required before execution.

---

### User Story 7 - System Health Monitoring and Self-Healing (Priority: P3)

The cloud agent continuously monitors its own health and the health of all watched services (Gmail API, social platform APIs, vault sync status). When a service degrades or a process crashes, the agent attempts auto-recovery (restart with backoff). If auto-recovery fails after configured retries, it creates an alert in `/Signals/health/` for the local agent to surface to the CEO.

**Why this priority**: An always-on system must be self-healing. Without health monitoring, silent failures accumulate.

**Independent Test**: Can be tested by simulating a process crash and verifying auto-restart behavior, then simulating persistent failure and verifying alert generation.

**Acceptance Scenarios**:

1. **Given** a watcher process crashes, **When** the health monitor detects the crash, **Then** the process is restarted within 30 seconds with exponential backoff.
2. **Given** a process fails to restart after 3 attempts, **When** all retries are exhausted, **Then** an alert file is created in `/Signals/health/` and the dashboard shows the degraded service.
3. **Given** the cloud VM's resource usage exceeds 80% CPU or memory, **When** the threshold is breached, **Then** a resource alert is created with recommendations.

---

### Edge Cases

- What happens when both agents attempt to modify the same approval file simultaneously? The conflict resolver applies the single-writer rule: local agent always wins for approval/execution files.
- What happens when the cloud VM runs out of disk space? The health monitor detects the threshold and creates an alert, then triggers log rotation and cleanup of old `/Done/` files.
- What happens when the local agent is offline for an extended period (days)? The cloud agent continues creating drafts and signals. Upon reconnection, vault sync processes the full queue without data loss, using timestamps to order operations.
- How does the system handle leaked or expired API tokens on the cloud side? The cloud agent only holds read-only tokens (no send/post/modify capability). Expiration triggers a signal to `/Signals/auth/` for the local agent to refresh credentials. A compromised cloud VM cannot perform any outbound actions.
- What happens when the vault Git repository has merge conflicts that the automatic resolver cannot handle? Unresolvable conflicts are flagged in `/Signals/sync/` with details, and the local agent notifies the CEO. The sync continues for non-conflicting files.

## Clarifications

### Session 2026-02-18

- Q: When should unapproved drafts automatically expire? → A: 48 hours — accommodates weekends/busy days while preventing stale draft accumulation.
- Q: How should vault sync be triggered between cloud and local agents? → A: Polling every 5 minutes — matches propagation target, low resource cost on free-tier VM.
- Q: What credential scope should the cloud agent hold for external APIs? → A: Read-only OAuth scopes only — cloud can monitor inboxes and read content calendars but cannot send, post, or modify anything.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST operate as two distinct agents — a cloud agent (always-on, untrusted zone) and a local agent (on-demand, trusted zone) — communicating exclusively through a synced Obsidian vault.
- **FR-002**: The cloud agent MUST NEVER have access to WhatsApp sessions, banking credentials, payment tokens, or any secrets classified as "sensitive" in the credential configuration. The cloud agent MUST only hold read-only OAuth scopes for external APIs (Gmail read-only, social platform read-only) — no send, post, or modify permissions.
- **FR-003**: The cloud agent MUST monitor Gmail for new emails, classify them by priority (high/medium/low), and create draft reply files in the vault within 5 minutes of receipt.
- **FR-004**: The vault synchronization MUST use Git-based polling sync every 5 minutes with automatic conflict resolution following single-writer rules (local wins for approvals, cloud wins for drafts).
- **FR-005**: The local agent MUST provide a dashboard showing all pending drafts, action items, alerts, and lead pipeline status.
- **FR-006**: All sensitive actions (sending emails, publishing social posts, executing payments) MUST only be executed by the local agent after explicit CEO approval.
- **FR-007**: The cloud agent MUST generate CEO briefings on a configurable schedule (default: Monday 7:00 AM) containing revenue, task velocity, subscription analysis, and upcoming deadlines.
- **FR-008**: The cloud agent MUST draft social media posts based on business goals and content calendar, creating platform-specific formatted drafts.
- **FR-009**: The system MUST capture and categorize leads from incoming emails with extracted company name, contact information, request type, and urgency classification.
- **FR-010**: The local agent MUST handle all payment execution through banking/payment APIs, with mandatory approval and configurable threshold-based secondary confirmation.
- **FR-011**: The cloud agent MUST self-monitor and auto-restart crashed processes with exponential backoff, creating alerts when auto-recovery fails.
- **FR-012**: The system MUST maintain an audit log of all actions taken by both agents, with tamper-evident hash chaining.
- **FR-013**: The vault sync MUST handle offline periods gracefully, queuing changes and processing the full queue upon reconnection without data loss.
- **FR-014**: The cloud agent MUST write to designated cloud directories only (`/Needs_Action/cloud/`, `/Drafts/`, `/Signals/`), and the local agent MUST write to designated local directories only (`/Pending_Approval/local/`, `/Approved/`, `/Done/`).
- **FR-015**: The system MUST support configurable notification channels for critical alerts (vault file, optional email/push notification).
- **FR-016**: Unapproved drafts MUST be automatically marked as expired after 48 hours, removed from the active dashboard queue, and archived to `/Done/expired/`.

### Key Entities

- **Agent**: Represents either the cloud or local agent instance. Attributes: agent-id, zone (cloud/untrusted, local/trusted), status (running/stopped/degraded), last-heartbeat, capabilities list.
- **Draft**: A proposed action created by the cloud agent awaiting approval. Attributes: draft-id, type (email-reply/social-post/payment/briefing), priority, created-at, expires-at (created-at + 48 hours), content, metadata, status (pending/approved/rejected/expired). Unapproved drafts are automatically marked expired after 48 hours.
- **Approval**: A decision record from the local agent. Attributes: approval-id, draft-id, decision (approved/rejected), feedback, decided-at, decided-by.
- **Lead**: A potential business opportunity extracted from email. Attributes: lead-id, source-email, company, contact, request-type, urgency, status, created-at.
- **SyncEvent**: A record of vault synchronization activity. Attributes: sync-id, direction (cloud-to-local/local-to-cloud), trigger (scheduled-poll/manual), files-changed, conflicts-resolved, timestamp, duration. Scheduled polls run every 5 minutes on both agents.
- **HealthCheck**: A system health snapshot. Attributes: check-id, agent, service-name, status (healthy/degraded/down), metric-values, timestamp, action-taken.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The cloud agent achieves 99.5% uptime over any 30-day period (max ~3.6 hours downtime/month).
- **SC-002**: New emails are detected and draft replies are created within 5 minutes of email arrival, 95% of the time.
- **SC-003**: Vault synchronization completes within 2 minutes of trigger, even after 24+ hours of offline accumulation.
- **SC-004**: The CEO can review and approve/reject any draft in under 30 seconds from the dashboard.
- **SC-005**: Zero sensitive credentials are ever stored on or accessible from the cloud agent.
- **SC-006**: Auto-recovery restores crashed processes within 2 minutes for 90% of recoverable failures.
- **SC-007**: Monday briefings are generated and available by 7:15 AM, covering all required data sections.
- **SC-008**: 100% of payment executions require explicit CEO approval before processing.
- **SC-009**: Lead capture correctly identifies and categorizes 80% of business inquiries from email.
- **SC-010**: All agent actions are recorded in the audit log with tamper-evident hash chains, with zero gaps.

## Assumptions

- The CEO has an existing Obsidian vault structure or is willing to adopt one.
- A free-tier cloud VM (Oracle Cloud or AWS) is available with sufficient resources (1 CPU, 1GB RAM minimum).
- Gmail API access is already configured or can be set up with OAuth2 credentials.
- Social media platform developer accounts and API access are available.
- Git is available on both cloud and local machines for vault synchronization.
- The local agent runs on a machine that is online at least once per business day.
- Payment sandbox/test environments are available for Stripe, PayPal, or bank transfer testing.
- The company has fewer than 500 emails/day (draft creation scales linearly).

## Constraints

- Cloud agent operates within free-tier VM resource limits (typically 1 vCPU, 1GB RAM, 50GB storage).
- No real-time bidirectional communication between agents — all interaction is async via vault sync.
- Local agent availability depends on the CEO's machine being online; cloud agent must function independently during offline periods.
- Sensitive credentials must never traverse the network to the cloud VM, even encrypted.

## Dependencies

- Gmail API (OAuth2) for email monitoring and sending.
- Social media platform APIs (LinkedIn, Twitter/X, Facebook) for post publishing.
- Git hosting service (GitHub/GitLab) for vault synchronization.
- Payment provider APIs (Stripe, PayPal) for payment execution (local agent only).
- Cloud VM provider (Oracle Cloud / AWS Free Tier) for cloud agent hosting.
- Existing Gold Tier skills (from `004-gold-tier-autonomous`) as foundation.
