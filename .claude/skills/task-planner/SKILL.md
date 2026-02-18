---
name: task-planner
description: Decomposes complex requests into actionable sub-tasks with dependency ordering, time estimates, risk assessment, and HITL approval checkpoints.
tools: []
tags:
  - planning
  - tasks
  - python
  - dependencies
  - approval
---

# Task Planner

Standalone Python skill that breaks complex requests into structured, dependency-ordered task plans with time estimates, risk levels, and approval checkpoints.

## Quick Start

```bash
# Using UV (recommended — auto-installs jinja2, pyyaml)
uv run task_planner.py --vault-path ../../obsidian-vault \
  --plan "Build landing page with contact form, deploy to production, send announcement email"

# Using pip
pip install -r requirements.txt
python task_planner.py --vault-path ../../obsidian-vault --plan "..."
```

## Task Decomposition Workflow

```
1. TRIGGER   → CLI --plan "request" or --detect finds Needs_Action/ request
2. PARSE     → Split request into action fragments (sentences, commas, lists)
3. CLASSIFY  → Assign each fragment to a phase (Setup → Core → Test → Deploy → Communicate)
4. DEPEND    → Build dependency graph, validate with topological sort (Kahn's)
5. ESTIMATE  → Keyword-based time estimation per task
6. RISK      → Assess risk levels, flag HITL approval for high-risk actions
7. RENDER    → Jinja2 template → TASKPLAN_{date}_{id}.md in plans/
8. APPROVE   → If high-risk tasks exist, create pending-approval/ file
9. LOG       → Append to Logs/task_plans.json
10. TRACK    → --progress and --update for ongoing monitoring
11. ARCHIVE  → --archive moves to Done/ when 100% complete
```

## Architecture

```
task-planner/
├── task_planner.py               # Main UV-runnable script (orchestrator)
├── dependency_resolver.py        # Topological sort + dependency validation
├── templates/
│   └── plan_template.md          # Jinja2 template for TASKPLAN output
├── requirements.txt
└── SKILL.md
```

## CLI Modes

```
--plan TEXT              Decompose a request into a task plan
--plan-file PATH         Read request from a file (e.g., from Needs_Action/)
--detect                 Scan Needs_Action/ for plannable requests
--progress PLAN_ID       Check completion progress for a plan
--update PLAN_ID TASK_ID Mark a task as done
--archive PLAN_ID        Move completed plan to Done/

--vault-path PATH        Obsidian vault path (default: ./obsidian-vault)
--verbose, -v            Enable debug logging
```

## Examples

```bash
# Decompose a multi-step request
uv run task_planner.py --vault-path ../../obsidian-vault \
  --plan "Set up CI/CD pipeline, add unit tests for auth module, deploy staging, and notify team"

# Read request from a file
uv run task_planner.py --vault-path ../../obsidian-vault \
  --plan-file ../../obsidian-vault/Needs_Action/PROJECT_new_feature.md

# Scan Needs_Action/ for plannable requests
uv run task_planner.py --vault-path ../../obsidian-vault --detect

# Check progress
uv run task_planner.py --vault-path ../../obsidian-vault --progress abc12345

# Mark task T001 as done
uv run task_planner.py --vault-path ../../obsidian-vault --update abc12345 T001

# Archive completed plan
uv run task_planner.py --vault-path ../../obsidian-vault --archive abc12345
```

## Phase Classification

Tasks are automatically classified into phases based on action keywords:

| Phase | Keywords | Icon |
|-------|----------|------|
| Setup & Configuration | install, setup, configure, initialize, provision, scaffold | 1. |
| Core Implementation | build, create, implement, develop, design, add, integrate | 2. |
| Testing & Verification | test, verify, validate, check, review, audit, qa | 3. |
| Deployment & Release | deploy, release, publish, launch, ship, push, migrate | 4. |
| Communication & Notification | send, email, notify, announce, post, share, report | 5. |

## Risk Assessment

| Risk Level | Keywords | Approval |
|------------|----------|----------|
| High | deploy, production, payment, delete, send, email, publish, migrate | Required |
| Medium | create, modify, configure, build, implement | Not required |
| Low | read, review, check, test, document, plan, draft | Not required |

## Time Estimation

Keyword-based estimates (adjustable):

| Action | Default Estimate |
|--------|-----------------|
| install | 0.25h |
| setup, configure | 0.5h |
| send, email, notify | 0.25h |
| test, verify | 0.5-0.75h |
| document, review | 0.75-1.0h |
| create, design, integrate | 1.0-1.5h |
| build, implement, develop | 2.0h |
| migrate | 1.5h |

## Dependency Resolution

Uses Kahn's algorithm (topological sort) for:

- **Ordering**: Tasks execute in dependency-respecting order
- **Cycle detection**: Catches circular dependencies before plan creation
- **Parallel groups**: Identifies tasks at the same topological level that can run concurrently
- **Critical path**: Computes the longest dependency chain for minimum completion time

## Vault Data Sources

| Source | Read/Write | Purpose |
|--------|------------|---------|
| `plans/TASKPLAN_*.md` | Write | Generated task plans |
| `Needs_Action/` | Read | Request detection (--detect) |
| `Done/` | Write | Archived completed plans |
| `pending-approval/` | Write | HITL approval requests for high-risk tasks |
| `Logs/task_plans.json` | Write | Event log |

## Output Format

Each task plan is a markdown file with:
- YAML frontmatter (type, id, title, status, progress tracking)
- Objective section
- Tasks grouped by phase with checkboxes
- Dependency annotations per task
- Time estimates and risk levels inline
- ASCII dependency graph
- Gantt-like ASCII timeline
- Approval checkpoints section
- Progress summary table

## Dependencies

- Python 3.10+
- `jinja2` — template rendering for plan output
- `python-dotenv` — .env loading
- `pyyaml` — YAML frontmatter parsing

All declared in PEP 723 script header for automatic UV resolution.
