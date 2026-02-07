# Research Findings: Personal AI Employee

## Claude Code Integration

### Decision: Use Claude Code CLI for processing files
- **Rationale**: Provides direct access to Claude's reasoning capabilities without complex API setup
- **Alternatives considered**:
  - API integration: More complex setup and authentication requirements
  - Direct Python bindings: Limited availability and documentation

### Implementation Pattern
- Claude Code can be called via subprocess or CLI for file processing
- Supports various output formats including JSON for structured responses
- Can be configured with custom prompts and instructions

## Python File System Monitoring

### Decision: Use python-watchdog library
- **Rationale**: Mature, reliable library for file system monitoring with cross-platform support
- **Alternatives considered**:
  - inotify (Linux only): Platform-specific solution limiting portability
  - pyinotify: Less mature than watchdog with fewer features
  - Built-in os.stat(): Requires manual polling which is inefficient

### Key Features
- Event-based monitoring rather than polling
- Cross-platform support (Windows, macOS, Linux)
- Recursive directory watching capabilities
- Various event types (create, modify, delete, move)

## Obsidian Vault Integration

### Decision: Direct file system access to vault directories
- **Rationale**: Obsidian vaults are standard file directories that can be accessed directly
- **Alternatives considered**:
  - Obsidian API/LiveSync: Requires premium subscription and introduces complexity
  - Obsidian HTTP Server plugin: Adds dependency on external plugin with potential security concerns

### Benefits
- Simple and reliable file access
- No external dependencies beyond file system permissions
- Full control over file operations
- Better auditability and logging capabilities

## Human-in-the-Loop Approval Workflows

### Decision: JSON-based approval request/response files
- **Rationale**: Fits with file-based architecture and provides clear audit trail
- **Alternatives considered**:
  - Database storage: Introduces complexity beyond Bronze tier requirements
  - In-memory storage: Doesn't persist across system restarts
  - Email notifications: Would require external communication (violates Bronze tier)

### Implementation
- Approval requests stored as JSON files in pending-approval directory
- Human operators review and modify files to indicate approval/rejection
- System monitors approval directory for responses
- Clear schema ensures consistency and validation

## Security Considerations for File-Based AI Systems

### Decision: Implement strict file path validation and directory boundaries
- **Rationale**: Prevents access to unauthorized files outside vault, ensuring security compliance
- **Alternatives considered**:
  - OS-level permissions: Provides system-level security but less granular control
  - Sandboxed execution: More complex to implement and manage

### Security Controls
- Path traversal prevention (checking for ../ sequences)
- Absolute path validation against allowed directories
- File extension filtering to prevent execution of scripts
- Size limits on files to prevent resource exhaustion
- Content scanning for potentially dangerous patterns

## Bronze Tier Compliance Verification

### Network Isolation
- Confirmed that python-watchdog operates within local file system only
- Claude Code CLI integration does not require network access for basic operations
- All communication happens through file exchanges

### External Action Prevention
- File-based architecture naturally restricts operations to local file system
- Approval workflows ensure human oversight for all operations
- Logging mechanisms provide complete audit trail

## Technology Stack Recommendations

### Core Components
- **Python 3.8+**: For main application logic and file processing
- **python-watchdog**: For file system monitoring
- **PyYAML**: For configuration file parsing
- **Standard library**: For file operations and JSON processing

### Optional Enhancements
- **colorama**: For enhanced console output during development
- **pytest**: For testing framework
- **mypy**: For static type checking

## Risk Assessment

### Identified Risks
1. **Path traversal attacks**: Mitigated by path validation
2. **Resource exhaustion**: Mitigated by file size limits
3. **Malicious file execution**: Mitigated by file type validation
4. **Insufficient audit logging**: Mitigated by comprehensive logging design

### Mitigation Strategies
- Input validation at all boundaries
- Principle of least privilege for file access
- Defense in depth with multiple validation layers
- Comprehensive error handling and logging