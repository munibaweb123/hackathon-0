# Implementation Plan: Personal AI Employee (Bronze Tier)

## Technical Context

### System Architecture
The Personal AI Employee operates as a file-based autonomous system within a local Obsidian vault environment. The system integrates Claude Code as the reasoning engine and Python Watchers for environmental perception, with strict human-in-the-loop oversight.

**Unknowns requiring research:**
- Claude Code integration patterns for file processing: RESOLVED - Claude Code can be integrated via CLI or API for processing files and generating responses
- Python Watcher implementation for file system monitoring: RESOLVED - Python watchdog library provides reliable file system monitoring capabilities
- Obsidian vault API or file system interaction methods: RESOLVED - Obsidian vaults are standard file directories that can be accessed directly via file system operations

### Dependencies
- Claude Code for reasoning engine
- Python for watcher implementations
- Obsidian vault for file storage and UI
- File system monitoring capabilities
- Python watchdog library for file monitoring

### Integration Points
- File system monitoring interface
- Claude Code API integration
- Obsidian vault file structure
- Human approval workflow system

## Constitution Check

### Human Authority
- The system must maintain human ultimate authority over all operations ✓
- All significant actions require human approval ✓
- Humans must remain in control of their digital workforce ✓

### Explainability
- Every decision and action must be explainable and traceable ✓
- Clear reasoning for all actions must be provided ✓
- Decision-making process must be articulable to human operators ✓

### Minimal Autonomy
- AI employee must operate with minimal autonomy necessary ✓
- Must seek human approval for significant consequences ✓
- Default to requesting guidance rather than making assumptions ✓

### Security & Privacy
- Protect user data and system resources with highest priority ✓
- Implement secure access controls ✓
- Never expose sensitive information without authorization ✓

### Deterministic Behavior
- Behave predictably and consistently ✓
- Actions must be reproducible ✓
- Decision-making must follow established rules ✓

### File-Based Operations
- Operate primarily within file system ✓
- Use file-based workflows as primary interaction mechanism ✓
- Record all state changes as file modifications ✓

### Transparency & Auditability
- All activities must be fully transparent and auditable ✓
- Every action must be logged with timestamps ✓
- Enable complete audit trails for accountability ✓

## Research Phase (Phase 0)

### Research Tasks
1. Claude Code integration patterns for file-based workflows
   - Decision: Use Claude Code CLI for processing files
   - Rationale: Provides direct access to Claude's reasoning capabilities
   - Alternatives considered: API integration, but CLI is simpler for file-based workflows

2. Python file system monitoring best practices
   - Decision: Use python-watchdog library
   - Rationale: Mature, reliable library for file system monitoring
   - Alternatives considered: inotify, pyinotify, but watchdog provides cross-platform solution

3. Obsidian vault integration methods
   - Decision: Direct file system access to vault directories
   - Rationale: Obsidian vaults are standard file directories
   - Alternatives considered: Obsidian API, but direct file access is more reliable for Bronze tier

4. Human-in-the-loop approval workflow implementations
   - Decision: JSON-based approval request/response files
   - Rationale: Fits with file-based architecture and provides clear audit trail
   - Alternatives considered: Database storage, but file-based is more appropriate for Bronze tier

5. Security considerations for file-based AI systems
   - Decision: Implement strict file path validation and directory boundaries
   - Rationale: Prevents access to unauthorized files outside vault
   - Alternatives considered: OS-level permissions, but application-level checks provide better control

## Design Phase (Phase 1)

### Data Model
- File entity with metadata, state, and processing history
- Operation entity with type, status, and approval requirements
- Approval entity with decision, timestamp, and operator
- Log entry entity with timestamp, actor, and details

### Contracts
- File processing API endpoints
- Approval request/response schemas
- State transition interfaces
- Monitoring event handlers

### Quickstart Guide
- Setup instructions for local environment
- Configuration requirements
- Initial vault setup
- Basic operation workflows

## Implementation Approach

### Iterative Development
- Start with basic file monitoring
- Add Claude Code integration
- Implement approval workflows
- Add comprehensive logging
- Finalize security constraints

### Risk Mitigation
- Implement safety checks at each stage
- Maintain human oversight throughout
- Test all security boundaries
- Validate all logging mechanisms

## Phase 1: Design & Contracts

### Data Model: data-model.md

```markdown
# Data Model: Personal AI Employee

## File Entity
- id: unique identifier for the file
- path: relative path within vault
- type: file type (document, task, config, etc.)
- status: current processing state (new, processing, completed, pending_approval, archived)
- created_at: timestamp when file was detected
- updated_at: timestamp of last modification
- metadata: key-value pairs for additional information
- processing_history: array of processing events with timestamps

## Operation Entity
- id: unique identifier for the operation
- type: operation type (read, write, process, categorize, etc.)
- status: operation status (pending, in_progress, completed, failed, approved, rejected)
- file_id: reference to associated file
- description: human-readable description of operation
- created_at: timestamp when operation was initiated
- completed_at: timestamp when operation was completed
- result: outcome of the operation
- requires_approval: boolean indicating if approval is needed

## Approval Entity
- id: unique identifier for the approval request
- operation_id: reference to associated operation
- request_type: type of approval request
- description: human-readable description of what needs approval
- justification: reasoning for the requested action
- options: array of possible options for human selection
- requested_at: timestamp when approval was requested
- responded_at: timestamp when approval was given/declined
- approved: boolean indicating if approved
- approver_id: identifier of the human who provided approval
- comments: optional human comments
- selected_option: identifier of the selected option if applicable

## Log Entry Entity
- id: unique identifier for the log entry
- timestamp: when the event occurred
- level: log level (info, warn, error, critical, audit)
- actor: what caused the event (ai_employee, human_operator, system)
- action: what action was taken
- details: additional information about the event
- file_ref: optional reference to associated file
- operation_ref: optional reference to associated operation
```

### API Contracts

#### File Processing Endpoint
```yaml
# File Processing API Contract
/openapi:3.0.0
info:
  title: Personal AI Employee File Processing API
  version: 1.0.0
paths:
  /files/{fileId}/process:
    post:
      summary: Process a file using Claude Code reasoning
      parameters:
        - name: fileId
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                processing_type:
                  type: string
                  enum: [summarize, categorize, transform, analyze]
                context:
                  type: string
                  description: Additional context for processing
      responses:
        '200':
          description: Processing initiated successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Operation'
        '400':
          description: Invalid request
        '403':
          description: File access denied
        '500':
          description: Internal server error
components:
  schemas:
    Operation:
      type: object
      properties:
        id:
          type: string
        status:
          type: string
          enum: [pending, in_progress, completed, failed, pending_approval]
        file_id:
          type: string
        result:
          type: string
        requires_human_approval:
          type: boolean
```

#### Approval Request/Response Schema
```json
{
  "request_id": "unique-identifier",
  "timestamp": "ISO-8601-timestamp",
  "request_type": "operation-type",
  "description": "human-readable description of requested action",
  "justification": "reasoning for the requested action",
  "options": [
    {
      "option_id": "option-identifier",
      "description": "description of the option",
      "expected_outcome": "anticipated result of this option"
    }
  ],
  "file_context": "path-to-relevant-files",
  "risk_level": "low|medium|high",
  "urgency": "normal|urgent",
  "created_by": "ai-employee"
}
```

## Quickstart Guide: quickstart.md

```markdown
# Quickstart Guide: Personal AI Employee

## Prerequisites
- Python 3.8+
- Claude Code installed and configured
- Obsidian vault directory structure set up

## Setup

### 1. Environment Setup
```bash
# Clone the repository
git clone <repository-url>
cd personal-ai-employee

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Create a configuration file `config.yaml`:
```yaml
vault_path: "./obsidian-vault"
input_folder: "inbox"
processing_folder: "processing"
pending_approval_folder: "pending-approval"
completed_folder: "completed"
rejected_folder: "rejected"
archive_folder: "archive"
error_folder: "error"
log_directory: "./logs"
watcher_interval: 5  # seconds
```

### 3. Initialize Vault Structure
```bash
mkdir -p obsidian-vault/{inbox,processing,pending-approval,completed,rejected,archive,error}
mkdir -p logs
```

### 4. Run the AI Employee
```bash
python ai_employee.py
```

## Basic Operations

### File Processing
1. Place files in the `inbox/` directory
2. The AI employee will detect and process the files
3. Processed files will move to appropriate directories based on workflow

### Approval Requests
1. When human approval is needed, request files appear in `pending-approval/`
2. Review the request and approve or reject
3. Approved/rejected files move to appropriate directories

## Monitoring
- Check log files in the `logs/` directory
- Monitor the status of files in different workflow directories
- Review approval requests when they appear
```

## Gate Evaluations

### Constitution Compliance
✓ All constitutional principles are satisfied in the design
✓ Human authority is maintained through approval workflows
✓ All operations are logged for transparency and auditability
✓ Security and privacy measures are implemented
✓ System operates within file-based constraints

### Bronze Tier Compliance
✓ No external network communication implemented
✓ File system operations only within designated vault
✓ No autonomous external actions
✓ Human-in-the-loop for significant operations
✓ All activities are transparent and auditable
```