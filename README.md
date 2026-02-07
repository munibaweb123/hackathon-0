# Personal AI Employee

Personal AI Employee (Digital FTE) - a file-based autonomous system that operates within a local Obsidian vault environment.

## Overview

The Personal AI Employee processes files, performs tasks, and manages workflows using Claude Code as the reasoning engine and Python Watchers for environmental perception. The system operates in Bronze Tier mode with strict human oversight and file-based operations only.

## Installation & Usage with uv

This project uses the `uv` package manager for fast dependency management and virtual environment handling.

### Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   # Or use: uv run python ...
   ```

### Running the AI Employee

1. **Quick start**:
   ```bash
   uv run python -m src.ai_employee
   ```

2. **Using the startup script**:
   ```bash
   ./start-ai-employee.sh
   ```

3. **Using the command line entry point**:
   ```bash
   uv run personal-ai-employee
   ```

### Development

For development, install with dev dependencies:
```bash
uv sync --extra dev
```

Then run tests:
```bash
uv run pytest
```

### Project Structure

- `src/` - Main source code
- `obsidian-vault/inbox/` - Place files here for AI to process
- `obsidian-vault/processing/` - Files being processed
- `obsidian-vault/completed/` - Successfully processed files
- `obsidian-vault/pending-approval/` - Files requiring human approval
- `logs/` - Audit logs