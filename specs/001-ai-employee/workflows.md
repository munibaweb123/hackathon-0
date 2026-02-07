# Workflows Specification - Personal AI Employee

## File Intake Workflow

1. **File Detection**: Python Watchers monitor designated input directories for new files
2. **File Classification**: Agent analyzes file type, content, and metadata to determine appropriate processing
3. **Priority Assignment**: Files are assigned priority based on type, urgency, and human-defined rules
4. **Queue Placement**: Files are placed in appropriate processing queues based on classification
5. **Status Update**: File intake status is logged with timestamp and initial assessment
6. **Human Notification**: If required, human operator is notified of new intake for approval

## Reasoning Workflow

1. **Request Analysis**: Agent parses the file content to understand the requested task or operation
2. **Context Gathering**: Agent collects relevant information from the vault to inform decision-making
3. **Rule Application**: Established processing rules are applied to determine appropriate actions
4. **Option Generation**: Multiple potential solutions are evaluated where applicable
5. **Decision Making**: Agent selects optimal approach based on rules, context, and human preferences
6. **Plan Formation**: Detailed execution plan is created with specific steps and expected outcomes
7. **Human Review**: If complexity threshold is exceeded, plan is submitted for human approval

## Planning Workflow

1. **Task Breakdown**: Complex requests are decomposed into smaller, manageable subtasks
2. **Resource Assessment**: Required resources and dependencies are identified
3. **Timeline Estimation**: Processing time is estimated based on task complexity
4. **Risk Evaluation**: Potential issues and failure points are identified
5. **Approval Requirements**: Tasks requiring human approval are flagged
6. **Execution Sequence**: Subtasks are ordered according to dependencies and priority
7. **Plan Documentation**: Execution plan is documented and stored for reference

## Human Review Workflow

1. **Trigger Detection**: System identifies tasks requiring human approval based on rules
2. **Request Formation**: Clear request with context and options is prepared for human review
3. **Notification**: Human operator is notified of pending approval request
4. **Review Interface**: Human is presented with relevant information and decision options
5. **Approval Process**: Human provides explicit approval, modification, or rejection
6. **Response Processing**: Human decision is recorded and appropriate actions are initiated
7. **Status Update**: Task status is updated to reflect human decision

## State Transitions Between Folders

### Input Folder (inbox/)
- Files arrive for processing
- Status: NEW
- Transition: Move to processing/ when intake workflow begins

### Processing Folder (processing/)
- Files being actively processed
- Status: IN_PROGRESS
- Transition: Move to pending-approval/ if human approval needed, or to completed/ if fully processed

### Pending Approval Folder (pending-approval/)
- Files requiring human decision
- Status: AWAITING_APPROVAL
- Transition: Move to processing/ after approval, or to rejected/ if rejected

### Completed Folder (completed/)
- Successfully processed files
- Status: COMPLETED
- Transition: Files remain unless archival rules apply

### Rejected Folder (rejected/)
- Files that were rejected or failed processing
- Status: REJECTED
- Transition: Files remain for review, with option to retry after human intervention

### Archive Folder (archive/)
- Completed files meeting archival criteria
- Status: ARCHIVED
- Transition: Files remain with potential for retrieval based on retention rules

## Error Handling at Spec Level

### File Processing Errors
- Invalid file format: Log error, move to error/ folder with error details
- Missing dependencies: Suspend processing, notify human operator, wait for resolution
- Processing timeout: Log timeout, move to error/ folder with timeout details
- Permission issues: Log permission error, halt processing, notify human operator

### System Errors
- Watcher failures: Log error, attempt restart, notify human operator if persistent
- Agent unavailability: Queue tasks, maintain status, resume when agent available
- Vault access issues: Suspend operations, notify human operator, wait for resolution
- Configuration errors: Log error, maintain safe state, wait for human correction

### Recovery Procedures
- Automatic retry: Simple errors are retried up to 3 times with exponential backoff
- Human intervention: Complex errors require human decision for resolution
- Safe state maintenance: System reverts to safe state when errors occur
- Audit trail: All errors and recovery actions are logged for review