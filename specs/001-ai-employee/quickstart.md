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