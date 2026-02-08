# Feature Specification: Gold Tier — Autonomous Employee

**Feature Branch**: `004-gold-tier-autonomous`
**Created**: 2026-02-08
**Status**: Draft
**Input**: User description: "Gold Tier: Autonomous Employee with full cross-domain integration (Personal + Business), Xero accounting integration, Facebook/Instagram/Twitter posting, multiple MCP servers, weekly CEO briefings, error recovery, comprehensive audit logging, and Agent Skills architecture"

**Prerequisites**: Silver Tier (003-silver-tier-assistant) must be complete. Gold Tier extends Silver with:
- Cross-domain integration (personal + business contexts)
- External accounting system (Xero)
- Social media platforms (Facebook, Instagram, Twitter/X)
- Multi-MCP server architecture
- Scheduled business intelligence reporting

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Xero Accounting Integration (Priority: P1) 🎯 MVP

The AI Employee connects to the business owner's Xero accounting system and monitors financial data. When the owner asks about business finances, invoice status, or expense summaries, the system retrieves accurate data from Xero and presents it in a clear format. The AI can create invoices, record expenses, and reconcile transactions after human approval.

**Why this priority**: Accounting integration is the core differentiator for Gold Tier. It enables autonomous business operations and is required for weekly CEO briefings. Without financial data access, the autonomous employee cannot provide meaningful business oversight.

**Independent Test**: Connect Xero account via OAuth, query current invoices, create a test invoice draft, verify data appears correctly. CEO briefing can use this data immediately.

**Acceptance Scenarios**:

1. **Given** a connected Xero account, **When** the user asks "What invoices are outstanding?", **Then** the system retrieves and displays all unpaid invoices with amounts and due dates
2. **Given** a connected Xero account, **When** the AI generates a weekly audit, **Then** the system includes accurate revenue, expenses, and cash flow data from Xero
3. **Given** a draft invoice created by the AI, **When** the user approves it, **Then** the invoice is created in Xero and the customer is notified
4. **Given** a bank transaction in Xero, **When** the AI suggests a category match, **Then** the user can approve or modify the categorization

---

### User Story 2 - Weekly CEO Briefing Generation (Priority: P1) 🎯 MVP

Every week, the AI Employee automatically generates a comprehensive CEO Briefing document that summarizes business health, financial status, social media performance, pending actions, and recommended priorities. The briefing is delivered to the owner for review before their weekly planning.

**Why this priority**: The CEO briefing is the primary value proposition for Gold Tier—transforming the AI from a reactive assistant into a proactive business advisor. It synthesizes data from all connected systems.

**Independent Test**: Trigger a briefing generation manually, verify it includes sections for financial summary (from Xero), social media metrics, pending approvals, and AI recommendations.

**Acceptance Scenarios**:

1. **Given** configured weekly schedule (e.g., Sunday 8 AM), **When** the scheduled time arrives, **Then** the system generates a CEO Briefing document in the vault
2. **Given** connected Xero and social accounts, **When** the briefing generates, **Then** it includes accurate financial metrics and social engagement data
3. **Given** pending approval requests older than 3 days, **When** the briefing generates, **Then** it highlights stale items requiring attention
4. **Given** significant variances (e.g., 20%+ revenue change), **When** detected, **Then** the briefing flags them with AI analysis and recommendations

---

### User Story 3 - Facebook & Instagram Integration (Priority: P2)

The AI Employee monitors the business's Facebook Page and Instagram Business account for messages, comments, and mentions. It can create and publish posts to both platforms with unified content management. Social performance data feeds into the weekly CEO briefing.

**Why this priority**: Meta platforms (Facebook/Instagram) represent the largest social advertising and engagement ecosystem. Integration provides significant reach for business content and customer engagement.

**Independent Test**: Connect Facebook/Instagram via OAuth, monitor for new messages, create a test post draft, verify approval workflow before publishing.

**Acceptance Scenarios**:

1. **Given** a connected Facebook Page, **When** a customer sends a message, **Then** the system creates an event file and can propose a response for approval
2. **Given** a connected Instagram Business account, **When** the AI generates a post, **Then** it can be published to both Facebook and Instagram simultaneously
3. **Given** published posts from the past week, **When** the CEO briefing generates, **Then** it includes engagement metrics (likes, comments, reach)
4. **Given** a post exceeds engagement thresholds, **When** detected, **Then** the AI suggests follow-up actions (respond to comments, boost post)

---

### User Story 4 - Twitter (X) Integration (Priority: P2)

The AI Employee connects to the business's Twitter/X account to monitor mentions and direct messages. It can compose tweets and threads, manage engagement, and track brand sentiment. Twitter activity data feeds into the CEO briefing.

**Why this priority**: Twitter/X provides real-time brand presence and customer service capabilities. It complements Meta platforms for comprehensive social coverage.

**Independent Test**: Connect Twitter via OAuth, monitor mentions, create a test tweet draft, verify approval workflow and rate limit handling.

**Acceptance Scenarios**:

1. **Given** a connected Twitter account, **When** someone mentions the business, **Then** the system creates an event file for review
2. **Given** approved tweet content, **When** published, **Then** the system records the tweet ID and tracks engagement
3. **Given** a DM requiring response, **When** the AI drafts a reply, **Then** it requires human approval before sending
4. **Given** weekly activity, **When** the CEO briefing generates, **Then** it includes follower growth, engagement rate, and top-performing tweets

---

### User Story 5 - Multi-MCP Server Architecture (Priority: P2)

The system operates multiple specialized MCP servers for different action domains: Social (Facebook, Instagram, Twitter), Financial (Xero), Communication (Email, WhatsApp), and a Coordinator that routes requests. This separation provides security boundaries and allows independent scaling.

**Why this priority**: Multi-MCP architecture enables secure isolation between sensitive domains (financial vs. social) and provides clear audit boundaries. It's foundational for enterprise-grade autonomy.

**Independent Test**: Start all MCP servers, verify health checks pass, execute an action through the coordinator, confirm routing to correct specialized server.

**Acceptance Scenarios**:

1. **Given** all MCP servers running, **When** an approved Xero action executes, **Then** only the Financial MCP server processes it
2. **Given** a server failure, **When** detected, **Then** the coordinator marks it unhealthy and prevents routing until recovery
3. **Given** concurrent actions across domains, **When** executed, **Then** each domain's rate limits are independently managed
4. **Given** an action request, **When** logged, **Then** the audit trail includes which MCP server processed it

---

### User Story 6 - Error Recovery & Graceful Degradation (Priority: P3)

When external services fail (API errors, rate limits, auth expiry), the AI Employee continues operating with reduced functionality rather than failing completely. It queues failed actions for retry, alerts the user to issues, and maintains core vault-based operations even when integrations are unavailable.

**Why this priority**: Reliability is essential for autonomous operation. Users must trust that the system won't lose data or silently fail when external services have issues.

**Independent Test**: Simulate API failure for one platform, verify the system continues operating other platforms, check that failed action is queued and retry succeeds when service recovers.

**Acceptance Scenarios**:

1. **Given** Xero API returns 503, **When** an invoice action fails, **Then** the action is queued for retry with exponential backoff
2. **Given** Twitter rate limit exceeded, **When** a tweet fails, **Then** the user is notified and the tweet is scheduled for retry after the limit resets
3. **Given** all social APIs unavailable, **When** the CEO briefing generates, **Then** it completes with a warning noting unavailable data sources
4. **Given** OAuth token expiry, **When** detected, **Then** the user is prompted to re-authenticate and pending actions are preserved

---

### User Story 7 - Cross-Domain Context Integration (Priority: P3)

The AI Employee maintains awareness across personal and business contexts. When processing an event, it considers relevant context from other domains (e.g., a LinkedIn message about a potential client can reference their invoice history from Xero, or a Twitter complaint can link to their email support thread).

**Why this priority**: Cross-domain intelligence is what distinguishes Gold Tier from simple integrations. It enables truly intelligent autonomous operation.

**Independent Test**: Create a scenario where a contact appears in multiple systems, verify the AI's response incorporates context from all relevant sources.

**Acceptance Scenarios**:

1. **Given** a customer in both Xero and email history, **When** they send a LinkedIn message, **Then** the AI's analysis includes their invoice status and past communication
2. **Given** a social media complaint, **When** the AI generates a response plan, **Then** it checks for existing support tickets or recent orders
3. **Given** a new business inquiry, **When** processing, **Then** the AI can propose creating entries in both CRM (vault) and Xero

---

### User Story 8 - Comprehensive Audit Logging (Priority: P3)

Every action, decision, and external API call is logged with tamper-evident hashing. Audit logs capture who (user or AI), what (action details), when (timestamp), why (context/reasoning), and the outcome. Logs can be exported for compliance and review.

**Why this priority**: Audit logging ensures accountability and enables troubleshooting. It's essential for trust in autonomous operations and potential regulatory compliance.

**Independent Test**: Execute several actions across different domains, export the audit log, verify completeness and hash chain integrity.

**Acceptance Scenarios**:

1. **Given** any MCP action executed, **When** logged, **Then** the log includes action type, approval reference, execution result, and timestamp
2. **Given** a sequence of logged events, **When** reviewed, **Then** each entry's hash includes the previous entry's hash (chain integrity)
3. **Given** a date range, **When** exporting audit logs, **Then** the export includes all relevant entries in a reviewable format
4. **Given** an external API call, **When** logged, **Then** the log includes request summary, response status, and latency

---

### Edge Cases

- What happens when Xero subscription expires mid-operation?
  - System detects 401/403 responses, marks Xero integration as "auth_required", notifies user, continues other operations
- How does the system handle conflicting information across platforms?
  - AI flags discrepancies in Plan.md with "[CONFLICT DETECTED]" and requests human guidance
- What if a social platform changes its API?
  - System detects unexpected responses, enters degraded mode for that platform, creates maintenance alert
- How are rate limits across multiple platforms coordinated?
  - Each MCP server tracks its own rate limits; coordinator aggregates status for dashboard display
- What happens when CEO briefing data is incomplete?
  - Briefing generates with "[DATA UNAVAILABLE: source]" markers and proceeds with available data

---

## Requirements *(mandatory)*

### Functional Requirements

#### Xero Integration
- **FR-001**: System MUST authenticate with Xero using OAuth 2.0 via the Xero MCP Server
- **FR-002**: System MUST retrieve invoices, contacts, bank transactions, and account balances from Xero
- **FR-003**: System MUST create draft invoices in Xero after human approval
- **FR-004**: System MUST categorize bank transactions with AI-suggested matches requiring approval
- **FR-005**: System MUST handle Xero API rate limits (60 calls/minute) with queuing

#### Social Media Integration
- **FR-006**: System MUST authenticate with Facebook/Instagram via Meta Business API OAuth
- **FR-007**: System MUST authenticate with Twitter/X via Twitter API v2 OAuth 2.0
- **FR-008**: System MUST monitor incoming messages and mentions from all connected social platforms
- **FR-009**: System MUST create and publish posts to social platforms after human approval
- **FR-010**: System MUST track engagement metrics (likes, comments, shares, reach) for published content

#### CEO Briefing
- **FR-011**: System MUST generate weekly CEO Briefing documents on a configurable schedule
- **FR-012**: CEO Briefing MUST include financial summary from Xero (revenue, expenses, cash flow, outstanding invoices)
- **FR-013**: CEO Briefing MUST include social media performance metrics from all connected platforms
- **FR-014**: CEO Briefing MUST highlight pending approvals and stale items requiring attention
- **FR-015**: CEO Briefing MUST include AI-generated insights and recommended actions

#### Multi-MCP Architecture
- **FR-016**: System MUST operate separate MCP servers for different action domains (Social, Financial, Communication)
- **FR-017**: System MUST route actions to appropriate MCP server based on action type
- **FR-018**: System MUST track health status of all MCP servers independently
- **FR-019**: System MUST prevent routing to unhealthy MCP servers

#### Error Handling & Recovery
- **FR-020**: System MUST queue failed actions for retry with exponential backoff
- **FR-020a**: System MUST retry failed actions up to 5 times with exponential backoff (max delay 4 hours between retries)
- **FR-020b**: System MUST mark actions as permanently failed after 5 unsuccessful retry attempts and notify the user
- **FR-021**: System MUST notify users of integration failures within 5 minutes
- **FR-022**: System MUST continue vault-based operations when external APIs are unavailable
- **FR-023**: System MUST detect and prompt for re-authentication when OAuth tokens expire

#### Audit & Compliance
- **FR-024**: System MUST log all MCP actions with tamper-evident hashes
- **FR-025**: System MUST maintain hash chain integrity across audit log entries
- **FR-026**: System MUST support audit log export for specified date ranges
- **FR-027**: System MUST log external API calls with request/response summaries
- **FR-027a**: System MUST retain audit logs in active storage for 90 days
- **FR-027b**: System MUST archive audit logs older than 90 days to cold storage indefinitely

#### Observability
- **FR-028**: System MUST emit structured logs (JSON format) for all significant operations
- **FR-029**: System MUST expose key metrics: API call latencies (p50, p95, p99), error rates per integration, retry queue depth
- **FR-030**: System MUST provide a health check endpoint aggregating all MCP server statuses

#### Credential Security
- **FR-031**: System MUST store OAuth tokens and API credentials encrypted in environment variables or a secrets manager (not plain text in vault files)
- **FR-032**: System MUST NOT log or expose credentials in audit entries or error messages

#### Cross-Domain Contact Matching
- **FR-033**: System MUST match contacts across platforms using email address as the primary key
- **FR-034**: System MUST support manual contact linking via dashboard when email matching is unavailable
- **FR-035**: System MUST maintain a unified contact profile that aggregates data from all linked platform identities

#### Agent Skills Architecture
- **FR-036**: All AI functionality MUST be implemented as Agent Skills
- **FR-037**: System MUST include XeroSkill for financial operations
- **FR-038**: System MUST include FacebookSkill and InstagramSkill for Meta platform operations
- **FR-039**: System MUST include TwitterSkill for X platform operations
- **FR-040**: System MUST include CEOBriefingSkill for report generation
- **FR-041**: System MUST include AuditSkill for comprehensive logging

### Key Entities

- **XeroConnection**: OAuth credentials, tenant ID, token expiry, connection status for Xero integration
- **SocialAccount**: Platform type (facebook/instagram/twitter), OAuth tokens, account ID, follower count, connection status
- **CEOBriefing**: Generated report with financial summary, social metrics, pending actions, AI insights, generation timestamp
- **AuditEntry**: Action type, actor (user/AI), timestamp, details, result, previous hash, current hash
- **MCPServer**: Server ID, domain (social/financial/communication), status, endpoint, last health check
- **RetryQueue**: Failed action details, failure reason, retry count, next retry time, max retries

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can connect Xero account and view financial summary within 5 minutes of initial setup
- **SC-002**: CEO Briefing generates automatically on schedule with 95% reliability (no more than 2 missed generations per year)
- **SC-003**: Social media posts publish within 60 seconds of approval across all connected platforms
- **SC-004**: Failed actions retry successfully within 4 hours of service recovery (90% success rate)
- **SC-005**: Audit log hash chain validates with 100% integrity for all entries
- **SC-006**: System continues core operations (vault, email monitoring) when 1 or more integrations are unavailable
- **SC-007**: Users receive failure notifications within 5 minutes of integration errors
- **SC-008**: Cross-domain context appears in AI reasoning for 80% of multi-platform contacts
- **SC-009**: Weekly CEO Briefing includes data from at least 3 integrated sources (Xero + 2 social platforms)
- **SC-010**: All AI operations are traceable to specific Agent Skills in audit logs

---

## Assumptions

1. **Silver Tier Complete**: Gold Tier builds upon fully functional Silver Tier (Gmail, LinkedIn, WhatsApp watchers, approval workflow, reasoning loop, scheduling)
2. **Xero Account Available**: User has an active Xero subscription with API access enabled
3. **Social Business Accounts**: User has business/creator accounts (not personal) for Facebook, Instagram, and Twitter
4. **OAuth Permissions**: User can grant the required OAuth scopes for each platform
5. **Network Connectivity**: System operates in an environment with reliable internet access
6. **Single Business Context**: The system manages one business entity across all integrations (not multi-tenant)
7. **Weekly Briefing Timing**: Default CEO briefing schedule is Sunday 8:00 AM local time (configurable)
8. **Rate Limit Budgets**: Standard API rate limits apply (Xero: 60/min, Twitter: 300 tweets/3hrs, Meta: 200 calls/hr)

---

## Clarifications

### Session 2026-02-08

- Q: How should OAuth tokens and API credentials for external services (Xero, Meta, Twitter) be stored at rest? → A: Encrypted in environment variables / secrets manager
- Q: How should contacts be matched/deduplicated across platforms (e.g., same person on LinkedIn, Twitter, and Xero)? → A: Match by email address as primary key, manual linking for others
- Q: What is the expected audit log retention period before archival or deletion? → A: 90 days active, then archive to cold storage indefinitely
- Q: What observability signals should the system emit beyond audit logs? → A: Structured logs + key metrics (latencies, error rates, queue depths)
- Q: What is the maximum retry attempts for failed actions before marking them as permanently failed? → A: 5 retries with exponential backoff, max delay 4 hours

---

## Out of Scope

1. **Multi-tenant/Multi-business Support**: System supports one business entity only
2. **Payment Processing**: Xero integration reads data and creates invoices but does not process payments
3. **Ad Campaign Management**: Social integration covers organic content only, not paid advertising
4. **Direct CRM Integration**: Contact management uses vault files, not external CRM systems
5. **Mobile App**: Dashboard is web-only; no native mobile application
6. **Real-time Chat**: Social monitoring is poll-based (5-minute intervals), not real-time streaming
7. **Advanced Analytics**: CEO briefing provides summaries; detailed analytics dashboards are out of scope
8. **Compliance Certifications**: System provides audit logs but does not guarantee SOC2/GDPR certification
