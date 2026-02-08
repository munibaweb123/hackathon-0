# Feature Specification: Silver Tier — Functional Assistant

**Feature Branch**: `003-silver-tier-assistant`
**Created**: 2026-02-07
**Status**: Draft
**Input**: User description: "Silver Tier: Functional Assistant — All Bronze requirements plus watchers, LinkedIn auto-posting, Claude reasoning loop, MCP server, human-in-the-loop approval, scheduling, and Agent Skills"

## Architecture Pattern

The Silver Tier follows a **Perception → Reasoning → Action** pipeline:

1. **Perception (Watchers)**: Python watcher scripts monitor external platforms (Gmail via OAuth API, LinkedIn via OAuth API, WhatsApp via Playwright web automation). Each watcher creates structured event files (e.g., `EMAIL_*.md`, `LINKEDIN_*.md`, `WHATSAPP_*.md`) in the vault inbox folder.
2. **Reasoning (Claude Loop)**: Claude reasoning loop picks up new event files, analyzes them, and generates `Plan.md` files with recommended actions and approval checkboxes.
3. **Action (MCP Server)**: Approved actions are executed through MCP server tools — the "hands" of the AI Employee. MCP servers handle outbound operations like sending emails, publishing LinkedIn posts, and replying to WhatsApp messages.

Human approval gates sit between Reasoning and Action — no external action executes without explicit human consent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Channel Monitoring via Watchers (Priority: P1)

As a business owner, I want the AI Employee to automatically monitor my Gmail inbox, WhatsApp messages, and LinkedIn activity, so that I am alerted to important communications without manually checking each platform.

**Why this priority**: Watchers are the foundation of the Silver Tier — they enable the AI Employee to perceive the external world beyond the local file system. Without them, no downstream automation (posting, reasoning, approvals) can function.

**Independent Test**: Can be tested by connecting Gmail and LinkedIn accounts, sending a test email, and verifying the system detects and logs the event to the vault within the configured polling interval.

**Acceptance Scenarios**:

1. **Given** Gmail is authenticated via OAuth, **When** a new email arrives in the inbox, **Then** the system detects it within the polling interval and creates a structured event file in the vault inbox.
2. **Given** LinkedIn is authenticated via OAuth, **When** the user's profile receives activity (connection requests, messages), **Then** the system logs a structured event in the vault.
3. **Given** WhatsApp is connected via Playwright-based web automation, **When** a new message is received, **Then** the system captures the message and creates a vault event file.
4. **Given** a watcher loses connectivity or credentials expire, **When** the next polling cycle runs, **Then** the system logs an error and falls back to mock mode without crashing.

---

### User Story 2 - Automated LinkedIn Posting for Business Sales (Priority: P1)

As a business owner, I want the AI Employee to automatically create and publish LinkedIn posts about my business to generate sales leads, so that my professional presence is maintained without manual effort.

**Why this priority**: LinkedIn auto-posting is a core Silver Tier deliverable that directly generates business value. It demonstrates the AI Employee's ability to take external actions on the user's behalf.

**Independent Test**: Can be tested by triggering a post creation, verifying the content appears on the user's LinkedIn profile, and confirming the post is logged locally with a "published" status.

**Acceptance Scenarios**:

1. **Given** the user has connected their LinkedIn account, **When** a scheduled posting time arrives, **Then** the system generates business-relevant content and publishes it to LinkedIn.
2. **Given** a post is scheduled, **When** the content is generated, **Then** the system presents it for human approval before publishing (all posts require approval in Silver Tier).
3. **Given** a post is successfully published, **When** the LinkedIn API confirms success, **Then** the system logs the post with its ID, content, timestamp, and "published" status.
4. **Given** a post fails to publish, **When** the API returns an error, **Then** the system logs the failure, retains the content, and alerts the user.

---

### User Story 3 - Claude Reasoning Loop with Plan.md Generation (Priority: P2)

As a business owner, I want the AI Employee to use a Claude-powered reasoning loop to analyze incoming events and generate Plan.md files with recommended actions, so that I can review and approve structured plans rather than raw data.

**Why this priority**: The reasoning loop transforms raw watcher data into actionable plans, making the AI Employee genuinely useful rather than just a notification system.

**Independent Test**: Can be tested by placing a test event file in the vault inbox and verifying that the system produces a well-structured Plan.md with context, analysis, recommended actions, and approval checkboxes.

**Acceptance Scenarios**:

1. **Given** a new event file appears in the vault inbox, **When** the reasoning loop processes it, **Then** a Plan.md file is created in the appropriate folder with context, analysis, and recommended next steps.
2. **Given** the reasoning loop encounters an event it cannot classify, **When** processing completes, **Then** it generates a plan requesting human clarification rather than taking autonomous action.
3. **Given** multiple related events arrive in sequence, **When** the reasoning loop processes them, **Then** it groups them into a single coherent plan rather than generating duplicate plans.

---

### User Story 4 - MCP Server for External Actions (Priority: P2)

As a business owner, I want the AI Employee to execute approved external actions (such as sending emails) through a controlled MCP server, so that the system can act on my behalf while maintaining security boundaries.

**Why this priority**: The MCP server is the gateway for all external actions, making it essential for LinkedIn posting, email sending, and other outbound operations.

**Independent Test**: Can be tested by submitting an approved email action through the MCP server and verifying the email is sent to the intended recipient.

**Acceptance Scenarios**:

1. **Given** an action is approved by the human operator, **When** the MCP server receives the execution request, **Then** it validates the approval, executes the action, and logs the result.
2. **Given** an action is submitted without valid approval, **When** the MCP server processes it, **Then** it rejects the action and logs the unauthorized attempt.
3. **Given** an external action fails (network error, API limit), **When** the MCP server detects the failure, **Then** it logs the error and notifies the user without retrying automatically.

---

### User Story 5 - Human-in-the-Loop Approval Workflow (Priority: P1)

As a business owner, I want to review and approve or reject sensitive actions proposed by the AI Employee, so that no consequential external action occurs without my explicit consent.

**Why this priority**: Human oversight is a constitutional requirement. Without approval workflows, the system cannot safely perform any external action.

**Independent Test**: Can be tested by triggering a sensitive action (e.g., email send), verifying an `APPROVAL_REQUIRED_*.md` file appears in the pending-approval folder, moving it to the `/Approved` folder, and confirming the action executes.

**Acceptance Scenarios**:

1. **Given** the AI Employee proposes a sensitive action, **When** the action is classified as requiring approval, **Then** an `APPROVAL_REQUIRED_<action>.md` file is created in the pending-approval folder with full context, proposed action, and risk level.
2. **Given** a pending approval file exists, **When** the human moves it to the `/Approved` folder (via dashboard or file system), **Then** the system detects the approval, executes the action, and logs the result.
3. **Given** a pending approval exists, **When** the human rejects it (moves to `/Rejected` folder or marks rejected via dashboard), **Then** the action is cancelled, the rejection reason is logged, and the AI Employee adjusts future recommendations.
4. **Given** an approval has been pending for more than 24 hours, **When** the system checks, **Then** it sends a reminder notification without auto-approving.

---

### User Story 6 - Task Scheduling (Priority: P3)

As a business owner, I want the AI Employee to perform routine tasks on a schedule (e.g., daily LinkedIn posts, hourly email checks), so that monitoring and actions happen consistently without manual triggering.

**Why this priority**: Scheduling enables autonomous operation but depends on watchers, reasoning, and approval workflows being functional first.

**Independent Test**: Can be tested by configuring a schedule for Gmail polling every 5 minutes, waiting for two cycles, and verifying events are created at the expected intervals.

**Acceptance Scenarios**:

1. **Given** a watcher is configured with a polling interval, **When** the scheduler triggers, **Then** the watcher runs and processes any new events.
2. **Given** a LinkedIn posting schedule is configured (e.g., daily at 9 AM), **When** the scheduled time arrives, **Then** the system generates content and submits it for approval or auto-posts if pre-approved.
3. **Given** the system is restarted, **When** the scheduler initializes, **Then** it resumes from the configured schedule without duplicating missed tasks.

---

### User Story 7 - Agent Skills Architecture (Priority: P2)

As a developer, I want all AI functionality to be implemented as modular Agent Skills, so that capabilities can be independently developed, tested, and composed into workflows.

**Why this priority**: The Agent Skills architecture enables maintainability and extensibility, making it possible to add new capabilities without modifying core infrastructure.

**Independent Test**: Can be tested by invoking a single skill (e.g., ReasoningSkill) with test input and verifying it produces the expected output without requiring other skills.

**Acceptance Scenarios**:

1. **Given** a skill is registered in the system, **When** a workflow requires that capability, **Then** the skill is invoked with appropriate input and returns structured output.
2. **Given** a new skill is developed, **When** it follows the base skill interface, **Then** it can be registered and used without modifying existing skills or infrastructure.
3. **Given** a skill encounters an error, **When** execution fails, **Then** the error is logged and the workflow continues or gracefully degrades without crashing the system.

---

### Edge Cases

- What happens when OAuth tokens expire mid-operation? The system must detect expired tokens, log the error, and prompt the user to re-authenticate.
- What happens when the LinkedIn API rate limit is reached? The system must queue the post, log the rate limit, and retry after the cooldown period.
- What happens when the vault disk is full? The system must detect insufficient space, halt write operations, and alert the user.
- What happens when multiple watchers detect events simultaneously? The system must process events sequentially to avoid file conflicts.
- What happens when an approval request references a stale event (e.g., email already replied to)? The system must detect staleness and mark the approval as "expired."
- What happens when the WhatsApp Web session expires or the QR code needs re-scanning? The system must detect the disconnected state, log the error, and prompt the user to re-authenticate by scanning a new QR code.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST monitor Gmail for incoming emails via OAuth-authenticated API access, creating structured event files in the vault inbox.
- **FR-002**: System MUST monitor LinkedIn for profile activity and notifications via OAuth-authenticated API access.
- **FR-003**: System MUST monitor WhatsApp for incoming messages via Playwright-based web automation (WhatsApp Web), creating structured event files in the vault inbox.
- **FR-004**: System MUST automatically generate business-relevant LinkedIn posts using a user-provided business profile and key topics (configured in dashboard settings) and publish them via the LinkedIn API.
- **FR-005**: System MUST use a Claude-powered reasoning loop to analyze vault events and generate Plan.md files with recommended actions.
- **FR-006**: System MUST operate an MCP server capable of executing approved external actions (email sending, LinkedIn posting).
- **FR-007**: System MUST require human approval for all sensitive external actions before execution, using file-based approval workflow (`APPROVAL_REQUIRED_*.md` files moved to `/Approved` folder to authorize).
- **FR-008**: System MUST support configurable scheduling for watcher polling intervals and automated posting.
- **FR-009**: System MUST implement all AI capabilities as modular Agent Skills following a common base interface.
- **FR-010**: System MUST log all operations, decisions, approvals, and errors with timestamps for full auditability.
- **FR-011**: System MUST gracefully handle API failures, expired tokens, and network errors without crashing.
- **FR-012**: System MUST include all Bronze Tier capabilities (file processing, state management, vault governance).
- **FR-013**: System MUST provide a web dashboard for viewing watcher events, managing approvals, and monitoring system status.

### Key Entities

- **Watcher**: A background service that monitors an external platform (Gmail, LinkedIn, WhatsApp) and produces structured event files. Has a type, polling interval, authentication state, and last-check timestamp.
- **Event**: A structured record of external activity (email received, LinkedIn notification, WhatsApp message). Contains source type, timestamp, raw data, priority, and processing status.
- **Plan**: A Plan.md file generated by the reasoning loop containing context, analysis, recommended actions, and approval status. Links to the originating event(s).
- **Approval Request**: A structured markdown file (`APPROVAL_REQUIRED_<action>.md`) requesting human authorization. Contains the proposed action, context, risk level, and decision status. Approved by moving to `/Approved` folder; rejected by moving to `/Rejected` folder.
- **Agent Skill**: A modular capability unit (reasoning, planning, communication, execution) that follows a common interface and can be composed into workflows.
- **Schedule**: A configuration defining when watchers poll, when posts are generated, and when routine tasks execute. Includes interval, next-run time, and enabled status.
- **Post**: A LinkedIn content item created by the system. Contains text, creation timestamp, publication status (draft/approved/published/failed), and LinkedIn post ID.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 2 watchers (Gmail + LinkedIn) successfully detect and log external events within their configured polling intervals.
- **SC-002**: The system generates and publishes at least 1 LinkedIn post per day when scheduling is enabled, with content relevant to the user's business.
- **SC-003**: 100% of sensitive external actions require and receive human approval before execution.
- **SC-004**: The Claude reasoning loop produces a Plan.md file for at least 80% of incoming vault events within 60 seconds of detection.
- **SC-005**: The MCP server successfully executes approved actions (email send, LinkedIn post) with a success rate above 90%.
- **SC-006**: All system operations are logged with timestamps, enabling a complete audit trail.
- **SC-007**: The system recovers gracefully from API failures within 1 polling cycle without manual intervention.
- **SC-008**: All AI capabilities are implemented as independently testable Agent Skills.
- **SC-009**: The web dashboard displays real-time status for all connected platforms and pending approvals.

## Assumptions

- The user has or will create OAuth credentials for Gmail and LinkedIn.
- WhatsApp integration uses Playwright-based web automation against WhatsApp Web; the user must have an active WhatsApp account and be able to scan the QR code for session authentication.
- The user's business context is understood well enough by the reasoning loop to generate relevant LinkedIn content.
- Claude Code or Claude API is available as the reasoning engine.
- The system runs on a machine with internet connectivity for API access.
- The Bronze Tier (001-ai-employee) foundation is functional and stable.
- The dashboard (Next.js) is the primary interface for human oversight and approval.

## Scope

### In Scope
- Gmail, LinkedIn, and WhatsApp watcher integration
- Automated LinkedIn posting with business content generation
- Claude reasoning loop producing Plan.md files
- MCP server for controlled external actions
- Human-in-the-loop approval via dashboard and vault files
- Configurable task scheduling
- Modular Agent Skills architecture
- Web dashboard for monitoring and approvals

### Out of Scope
- Gold Tier features (multi-agent orchestration, advanced analytics)
- Payment processing or financial transactions
- Real-time chat interface with the AI Employee
- Mobile app or native desktop client
- Multi-user access control or team features
- Advanced NLP beyond Claude's standard capabilities

## Clarifications

### Session 2026-02-07

- Q: Where does the AI get business context for LinkedIn content generation? → A: User provides a business profile/description and key topics in dashboard settings, which the AI uses as a prompt seed.
- Q: Should LinkedIn posts require approval or can some auto-publish? → A: All LinkedIn posts require human approval before publishing in Silver Tier. No auto-approve.
- Q: How should WhatsApp integration work? → A: Via Playwright-based web automation against WhatsApp Web (not Meta Business Cloud API). User authenticates by scanning QR code. This aligns with the hackathon architecture guide.
- Q: What is the overall system architecture? → A: Perception → Reasoning → Action pipeline. Watchers (Python scripts) create event files in the vault, Claude reasoning loop generates Plan.md files, MCP servers execute approved actions.
- Q: How does the approval workflow operate? → A: File-based. The system creates `APPROVAL_REQUIRED_<action>.md` files. Human moves them to `/Approved` folder to authorize or `/Rejected` folder to deny. Dashboard provides UI for this, but file-system operations also work directly.
