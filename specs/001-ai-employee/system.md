# System Overview - Personal AI Employee

## Purpose and Scope

The Personal AI Employee (Digital FTE) is a file-based autonomous system designed to act as a digital worker that operates within a local Obsidian vault environment. The system processes files, performs tasks, and manages workflows using Claude Code as the reasoning engine and Python Watchers for environmental perception. The system is designed to augment human productivity while maintaining strict human oversight and control.

The Bronze Tier implementation focuses on establishing a foundation for safe, transparent AI operations within file-based constraints, with no external network communication or autonomous actions beyond the local file system.

## Non-Goals

- Network communication or external API calls
- Autonomous email, messaging, or social media interactions
- Financial transactions or payment processing
- Direct database connections or external service integrations
- Full cognitive autonomy without human oversight
- Cross-platform synchronization beyond file-based sharing
- Advanced multimedia processing beyond text-based operations

## High-Level Architecture

The system consists of three primary components:

1. **Obsidian Vault**: Centralized file-based storage and UI that serves as the memory and workspace for the AI employee
2. **Claude Code Engine**: Reasoning and processing layer that interprets requests and generates responses
3. **Python Watchers**: Perception layer that monitors file system changes and triggers appropriate responses

The architecture operates entirely within the local file system, with all state changes and communications occurring through file modifications in the vault structure.

## Operating Assumptions

- The system operates on a single-user, single-machine basis
- The Obsidian vault is the authoritative source for all information
- All operations must be reversible through file system operations
- Human operators have full administrative privileges and oversight
- The system operates in a trusted local environment
- Network connectivity is not required for core functionality

## Definitions

- **Agent**: The AI entity that processes requests and performs tasks using Claude Code reasoning
- **Watcher**: Python-based monitoring processes that detect file system changes and trigger responses
- **Vault**: The Obsidian-based file structure that serves as the AI employee's memory and workspace
- **Human**: The authorized user who maintains ultimate authority and oversight of the AI employee