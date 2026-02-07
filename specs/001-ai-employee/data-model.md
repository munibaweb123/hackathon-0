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